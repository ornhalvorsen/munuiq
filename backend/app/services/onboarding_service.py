"""
Business logic for each onboarding wizard step.

Step 1 (Entities): Discover locations/installations from munu data
Step 2 (Categories): LLM-assisted category mapping
Step 3 (Products): LLM-assisted product variant grouping
Step 4 (Integrations): Auto-match Planday departments to installations
Step 5 (Validate & Approve): Write approved mappings to production tables
"""

import json
import re
from app.database import execute_read_query
from app.claude_client import get_client
from app.config import settings
from app import management_db


# ─── Step 1: Entity Discovery ────────────────────────────────────────

def scan_entities(customer_id: int) -> dict:
    """Discover business units, installations, and revenue units for a customer."""
    entities = {"business_units": [], "installations": [], "revenue_units": []}

    # Business units
    try:
        cols, rows = execute_read_query(
            f"SELECT DISTINCT bu.business_unit_id, bu.business_unit_name "
            f"FROM munu.business_units bu WHERE bu.customer_id = {customer_id}"
        )
        entities["business_units"] = [dict(zip(cols, r)) for r in rows]
    except Exception as e:
        print(f"Onboarding: scan business_units failed — {e}")

    # Installations (locations)
    try:
        cols, rows = execute_read_query(
            f"SELECT DISTINCT i.installation_id, i.installation_name, i.address "
            f"FROM munu.installations i WHERE i.customer_id = {customer_id}"
        )
        installations = [dict(zip(cols, r)) for r in rows]
        # Auto-classify and clean up names
        for inst in installations:
            inst["display_name"] = _clean_entity_name(inst.get("installation_name", ""))
            inst["entity_type"] = _classify_entity(inst.get("installation_name", ""))
            inst["selected"] = True
        entities["installations"] = installations
    except Exception as e:
        print(f"Onboarding: scan installations failed — {e}")

    # Revenue units
    try:
        cols, rows = execute_read_query(
            f"SELECT DISTINCT ru.revenue_unit_id, ru.revenue_unit_name, ru.installation_id "
            f"FROM munu.revenue_units ru WHERE ru.customer_id = {customer_id}"
        )
        entities["revenue_units"] = [dict(zip(cols, r)) for r in rows]
    except Exception as e:
        print(f"Onboarding: scan revenue_units failed — {e}")

    return entities


def _clean_entity_name(name: str) -> str:
    """Strip common prefixes/suffixes from entity names."""
    # Remove common chain-level prefixes like "BrandName - "
    parts = name.split(" - ", 1)
    if len(parts) == 2 and len(parts[1]) > 3:
        return parts[1].strip()
    return name.strip()


def _classify_entity(name: str) -> str:
    """Classify an entity as store/event/webshop/closed from name patterns."""
    name_lower = name.lower()
    if any(w in name_lower for w in ["nett", "web", "online", "e-"]):
        return "webshop"
    if any(w in name_lower for w in ["event", "catering", "festival"]):
        return "event"
    if any(w in name_lower for w in ["closed", "stengt", "nedlagt", "old"]):
        return "closed"
    return "store"


# ─── Step 2: Category Mapping ────────────────────────────────────────

def propose_categories(customer_id: int) -> list[dict]:
    """Query article groups and propose category mappings using LLM."""
    # Get distinct article groups for this customer
    try:
        cols, rows = execute_read_query(
            f"SELECT DISTINCT a.article_group_name, a.article_subgroup_name, "
            f"count(*) as article_count "
            f"FROM munu.articles a WHERE a.customer_id = {customer_id} "
            f"GROUP BY a.article_group_name, a.article_subgroup_name "
            f"ORDER BY article_count DESC LIMIT 200"
        )
        groups = [dict(zip(cols, r)) for r in rows]
    except Exception:
        return []

    if not groups:
        return []

    # Get existing category map for reference
    existing_categories = []
    try:
        cols, rows = execute_read_query(
            "SELECT DISTINCT unified_category FROM munu.article_category_map LIMIT 100"
        )
        existing_categories = [r[0] for r in rows if r[0]]
    except Exception:
        pass

    # Get sample articles per group for context
    samples = {}
    for g in groups[:50]:
        group_name = g.get("article_group_name", "")
        if group_name and group_name not in samples:
            try:
                cols, rows = execute_read_query(
                    f"SELECT a.article_name FROM munu.articles a "
                    f"WHERE a.customer_id = {customer_id} "
                    f"AND a.article_group_name = '{group_name.replace(chr(39), chr(39)*2)}' "
                    f"LIMIT 5"
                )
                samples[group_name] = [r[0] for r in rows]
            except Exception:
                pass

    # Build LLM prompt
    groups_text = "\n".join(
        f"- Group: {g.get('article_group_name', 'N/A')} / Sub: {g.get('article_subgroup_name', 'N/A')} ({g.get('article_count', 0)} articles)"
        + (f"  Samples: {', '.join(samples.get(g.get('article_group_name', ''), []))}" if g.get('article_group_name', '') in samples else "")
        for g in groups
    )

    existing_text = ", ".join(existing_categories) if existing_categories else "None yet"

    prompt = f"""Map these restaurant POS article groups to unified categories.

Existing unified categories (reuse when appropriate): {existing_text}

Article groups to categorize:
{groups_text}

Return JSON array:
[{{"source_group": "...", "source_subgroup": "...", "proposed_category": "...", "confidence": 0.0-1.0}}]

Rules:
- Use clear, consistent category names (e.g., "Beverages > Soft Drinks", "Food > Burgers")
- Reuse existing categories when they match
- Confidence 0.9+ for exact matches, 0.7-0.9 for good matches, below 0.7 for uncertain
- Return ONLY the JSON array, no explanation"""

    try:
        client = get_client()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        # Parse JSON from response
        if text.startswith("```"):
            m = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
            if m:
                text = m.group(1).strip()
        mappings_raw = json.loads(text)
    except Exception as e:
        print(f"Onboarding: category LLM failed — {e}")
        return []

    # Convert to mapping records
    mappings = []
    for m in mappings_raw:
        source_key = f"{m.get('source_group', '')}|{m.get('source_subgroup', '')}"
        mappings.append({
            "customer_id": customer_id,
            "mapping_type": "category",
            "source_key": source_key,
            "source_label": m.get("source_group", ""),
            "proposed_value": m.get("proposed_category", "Uncategorized"),
            "confidence": m.get("confidence", 0.5),
            "status": "proposed",
        })

    # Save to DB
    management_db.create_mappings(mappings)
    return management_db.get_mappings(customer_id, "category")


# ─── Step 3: Product Grouping ────────────────────────────────────────

def propose_products(customer_id: int) -> list[dict]:
    """Query articles and propose product variant groupings using LLM."""
    try:
        cols, rows = execute_read_query(
            f"SELECT a.article_id, a.article_name, a.article_group_name, "
            f"a.article_subgroup_name, a.price "
            f"FROM munu.articles a WHERE a.customer_id = {customer_id} "
            f"ORDER BY a.article_group_name, a.article_name LIMIT 500"
        )
        articles = [dict(zip(cols, r)) for r in rows]
    except Exception:
        return []

    if not articles:
        return []

    # Process in batches of 100 for LLM
    all_mappings = []
    batch_size = 100
    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        batch_text = "\n".join(
            f"- [{a.get('article_id')}] {a.get('article_name', '')} (Group: {a.get('article_group_name', '')}, Price: {a.get('price', 'N/A')})"
            for a in batch
        )

        prompt = f"""Group these restaurant menu articles into base products, identifying variants, deals, test items, and admin entries.

Articles:
{batch_text}

Return JSON array:
[{{"article_id": ..., "base_product": "...", "product_type": "regular|variant|deal|test|admin", "confidence": 0.0-1.0}}]

Rules:
- Group size variants (e.g., "Burger Small", "Burger Large") under same base_product "Burger"
- Mark items with "test", "prøve", "admin" in name as type "test" or "admin"
- Mark combo/deal items as "deal"
- Return ONLY the JSON array"""

        try:
            client = get_client()
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            if text.startswith("```"):
                m = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
                if m:
                    text = m.group(1).strip()
            groupings = json.loads(text)
        except Exception as e:
            print(f"Onboarding: product LLM batch failed — {e}")
            continue

        for g in groupings:
            all_mappings.append({
                "customer_id": customer_id,
                "mapping_type": "product",
                "source_key": str(g.get("article_id", "")),
                "source_label": next(
                    (a["article_name"] for a in batch if str(a.get("article_id")) == str(g.get("article_id"))),
                    "",
                ),
                "proposed_value": json.dumps({
                    "base_product": g.get("base_product", ""),
                    "product_type": g.get("product_type", "regular"),
                }),
                "confidence": g.get("confidence", 0.5),
                "status": "proposed",
            })

    if all_mappings:
        management_db.create_mappings(all_mappings)
    return management_db.get_mappings(customer_id, "product")


# ─── Step 4: Integration Mapping ─────────────────────────────────────

def scan_integrations(customer_id: int) -> dict:
    """Check for Planday and CakeItEasy data, auto-match where possible."""
    result = {"planday": [], "cakeiteasy": []}

    # Planday department matching
    try:
        cols, rows = execute_read_query(
            f"SELECT DISTINCT pd.department_id, pd.department_name "
            f"FROM planday.departments pd WHERE pd.customer_id = {customer_id}"
        )
        departments = [dict(zip(cols, r)) for r in rows]

        # Get installations for fuzzy matching
        inst_cols, inst_rows = execute_read_query(
            f"SELECT i.installation_id, i.installation_name "
            f"FROM munu.installations i WHERE i.customer_id = {customer_id}"
        )
        installations = [dict(zip(inst_cols, r)) for r in inst_rows]

        for dept in departments:
            dept_name = dept.get("department_name", "").lower()
            best_match = None
            best_score = 0
            for inst in installations:
                inst_name = inst.get("installation_name", "").lower()
                # Simple overlap scoring
                score = _fuzzy_score(dept_name, inst_name)
                if score > best_score:
                    best_score = score
                    best_match = inst
            dept["matched_installation_id"] = best_match["installation_id"] if best_match and best_score > 0.5 else None
            dept["matched_installation_name"] = best_match["installation_name"] if best_match and best_score > 0.5 else None
            dept["match_confidence"] = best_score
        result["planday"] = departments
    except Exception:
        pass

    # CakeItEasy products
    try:
        cols, rows = execute_read_query(
            f"SELECT DISTINCT c.product_id, c.product_name "
            f"FROM cakeiteasy.products c WHERE c.customer_id = {customer_id} LIMIT 100"
        )
        result["cakeiteasy"] = [dict(zip(cols, r)) for r in rows]
    except Exception:
        pass

    return result


def _fuzzy_score(a: str, b: str) -> float:
    """Simple word-overlap similarity score."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    overlap = words_a & words_b
    return len(overlap) / max(len(words_a), len(words_b))


# ─── Step 5: Validation & Approval ───────────────────────────────────

def get_summary(customer_id: int) -> dict:
    """Get onboarding summary with counts and warnings."""
    categories = management_db.get_mappings(customer_id, "category")
    products = management_db.get_mappings(customer_id, "product")

    cat_approved = sum(1 for m in categories if m["status"] == "approved")
    cat_rejected = sum(1 for m in categories if m["status"] == "rejected")
    cat_pending = sum(1 for m in categories if m["status"] == "proposed")

    prod_approved = sum(1 for m in products if m["status"] == "approved")
    prod_rejected = sum(1 for m in products if m["status"] == "rejected")
    prod_pending = sum(1 for m in products if m["status"] == "proposed")

    warnings = []
    if cat_pending > 0:
        warnings.append(f"{cat_pending} category mappings still pending review")
    if prod_pending > 0:
        warnings.append(f"{prod_pending} product groupings still pending review")

    return {
        "categories": {
            "total": len(categories),
            "approved": cat_approved,
            "rejected": cat_rejected,
            "pending": cat_pending,
        },
        "products": {
            "total": len(products),
            "approved": prod_approved,
            "rejected": prod_rejected,
            "pending": prod_pending,
        },
        "warnings": warnings,
        "ready": cat_pending == 0 and prod_pending == 0,
    }


def approve_onboarding(customer_id: int, user_id: int) -> dict:
    """Finalize onboarding. Approved mappings are already in onboarding_mappings
    and automatically reflected in the sales_fact view."""
    categories = management_db.get_mappings(customer_id, "category")
    approved_cats = [m for m in categories if m["status"] == "approved"]

    # Clear query caches so new queries use updated category mappings
    from app import query_cache
    query_cache.clear_all()

    # Update onboarding state to completed
    state = management_db.get_onboarding_state(customer_id)
    if state:
        completed_steps = json.loads(state.get("completed_steps", "[]")) if isinstance(state.get("completed_steps"), str) else state.get("completed_steps", [])
        if "approved" not in completed_steps:
            completed_steps.append("approved")
        management_db.update_onboarding_state(
            customer_id, "completed", completed_steps,
        )

    return {
        "categories_written": len(approved_cats),
        "products_written": 0,
        "errors": [],
    }
