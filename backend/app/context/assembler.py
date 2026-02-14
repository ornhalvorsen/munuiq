"""
CTXE Context Assembler — loads YAML artifacts at startup, builds
per-question context for the LLM.

Domain detection → table selection → schema + rules + recipes + patterns.
"""

import re
from pathlib import Path
from typing import Any

import yaml

from app.context.entity_resolver import (
    resolve_locations, format_location_hints,
    resolve_products, format_product_hints,
)

# ---------------------------------------------------------------------------
# Module state (loaded once at startup)
# ---------------------------------------------------------------------------
_tables: dict[str, dict] = {}          # table_name -> metadata from schema_metadata.yaml
_global_rules: dict[str, str] = {}     # rule_key -> rule text
_join_recipes: dict[str, dict] = {}    # recipe_key -> {description, domains, sql}
_patterns: dict[str, dict] = {}        # pattern_key -> {question, domains, triggers, sql, ...}
_duckdb_syntax: str = ""               # compact DuckDB syntax reference
_taxonomy_prompt: str = ""             # product taxonomy for prompt injection
_loaded = False

# ---------------------------------------------------------------------------
# Domain detection regexes
# ---------------------------------------------------------------------------
_DOMAIN_RES: list[tuple[str, re.Pattern]] = [
    # Analytics domain — checked first for priority routing
    ("analytics", re.compile(
        r"\b(trend(?:ing|s)?|trailing|rolling|benchmark|fleet\s+avg|"
        r"how(?:'s|s)?\s+\w+\s+(?:doing|performing|trending)|"
        r"mix.{0,10}(?:vs|versus|fleet)|overall|summary|overview|kpi|"
        r"daypart|week[\s-]*over[\s-]*week|growth\s+rate|best.{0,5}(?:store|worst)|worst.{0,5}store|"
        r"labor\s+cost|efficiency|staffing|overstaffed|understaffed|"
        r"sick\s+leave|sykefrav[æe]r|egenmelding|absence\s+rate)\b",
        re.IGNORECASE,
    )),
    ("sales", re.compile(
        r"\b(revenue|omsetning|inntekt|turnover|sale[s]?|salg|sol[gd]t|sell|sold|order[s]?|bestill|net_amount|order_total|average\s+ticket|avg\s+ticket|payment|betaling|vipps|kort|cash|kontant)\b",
        re.IGNORECASE,
    )),
    ("products", re.compile(
        r"\b(product|produkt|article|artikkel|categor(?:y|ies)|kategori(?:er)?|bolle[r]?|sandwich|brod|kake[r]?|drikke|kaffe|latte|croissant|menu|meny|item[s]?|bundle)\b",
        re.IGNORECASE,
    )),
    ("locations", re.compile(
        r"\b(location|lokasjoner?|butik[k]?|outlet|store[s]?|sted|avdeling|by\s+store|by\s+location|per\s+sted|revenue.?unit|madla|kvadrat|majorstuen|skoyen|forus)\b",
        re.IGNORECASE,
    )),
    ("labor", re.compile(
        r"\b(labor|labour|shift|skift|vakt|arbeid|timer|hours?\s+worked|punchclock|punch.?clock|employee|ansatt|staffing|staff|efficiency|per\s+hour|per\s+time|overtid|overtime)\b",
        re.IGNORECASE,
    )),
    ("waste", re.compile(
        r"\b(waste|svinn|kast(?:et)?|thrown\s+away|shrinkage|discarded)\b",
        re.IGNORECASE,
    )),
    ("external", re.compile(
        r"\b(weather|v[æe]r|temperature|temperatur|rain|regn|precipitation|cruise|school\s+holiday|ferie|skolefri)\b",
        re.IGNORECASE,
    )),
    ("cakeiteasy", re.compile(
        r"\b(cakeiteasy|cake\s*it\s*easy|web\s+order|nettbestilling|cake\s+order)\b",
        re.IGNORECASE,
    )),
]

# Raw-signal detection — prevents analytics routing when present
_RAW_SIGNALS = re.compile(
    r"\b(specific\s+order|receipt|transaction\s+at\s+\d|individual\s+(?:order|item)|"
    r"who\s+(?:sold|served)|order\s+number|basket.{0,10}bought\s+together|"
    r"payment\s+type|vipps|kort|kontant|"
    r"specific\s+employee|individual\s+shift)\b",
    re.IGNORECASE,
)

# Tables to suppress when analytics domain is active (analytics replaces raw)
_ANALYTICS_SUPPRESSES = {
    "analytics": {
        "munu.orders", "munu.order_lines",  # suppressed by daily_location_sales
        "planday.punchclock_shifts",         # suppressed by daily_location_labor
    },
}

# Pattern trigger regexes — map question keywords to pattern keys
_PATTERN_TRIGGERS: list[tuple[re.Pattern, str]] = []


def _build_pattern_triggers():
    """Build regex triggers from patterns.yaml trigger keywords."""
    global _PATTERN_TRIGGERS
    _PATTERN_TRIGGERS.clear()

    trigger_map = {
        "revenue_per_labor_hour_monthly": re.compile(
            r"\b(revenue\s+per\s+(labor|labour)\s+hour|per\s+time|per\s+hour.*(store|location|butik)|efficiency.*(store|location)|labor.*revenue|labour.*revenue|sales\s+per\s+(labor|labour))\b",
            re.IGNORECASE,
        ),
        "category_trends_by_store": re.compile(
            r"\b((?:weekly|monthly|daily)\s+(?:sales|revenue|trend).*(?:store|location|butik)|(?:store|location|butik).*(?:weekly|monthly|daily)|category\s+(?:trend|performance).*(?:store|location))\b",
            re.IGNORECASE,
        ),
        "store_vs_store": re.compile(
            r"\b(compare\s+(?:\w+\s+){0,3}(?:and|vs|versus|mot)|side\s+by\s+side|(?:madla|kvadrat|forus|majorstuen)\s+(?:vs|versus|mot|and)\s+(?:madla|kvadrat|forus|majorstuen))\b",
            re.IGNORECASE,
        ),
        "yoy_category_by_store": re.compile(
            r"\b(year[\s-]+over[\s-]+year|yoy|vs\s+last\s+year|compared\s+to\s+(?:same\s+period\s+)?last\s+year|growth\s*%|i\s+fjor|mot\s+forrige\s+[åa]r)\b",
            re.IGNORECASE,
        ),
        "basket_analysis_product": re.compile(
            r"\b(basket|orders?\s+(?:contain|with|includ)|order\s+size\s+when|average\s+order.*(?:contain|includ)|how\s+many\s+orders)\b",
            re.IGNORECASE,
        ),
        "products_sold_together": re.compile(
            r"\b(sold\s+together|bought\s+(?:together|with)|co[\s-]*occurrence|pair(?:ed|ing)?\s+with|what\s+(?:goes|products?).*(?:together|with))\b",
            re.IGNORECASE,
        ),
        "waste_trends_by_location": re.compile(
            r"\b(waste|svinn|shrinkage).*\b(store|location|butik|weekly|monthly|trend)\b",
            re.IGNORECASE,
        ),
        "peak_hours_by_store": re.compile(
            r"\b(busiest\s+hour|peak\s+(?:hour|time)|hourly\s+(?:pattern|sales|revenue)|by\s+hour|weekday\s+vs\s+weekend|per\s+time\s+p[åa]\s+dagen)\b",
            re.IGNORECASE,
        ),
        "seasonal_product_performance": re.compile(
            r"\b(seasonal|sesong|jul|christmas|p[åa]ske|easter|fastelavn|halloween|valentines?).*\b(product|perform|revenue|sale|compare)\b",
            re.IGNORECASE,
        ),
        "cumulative_revenue_by_store": re.compile(
            r"\b(cumulative|running\s+total|ytd|year\s+to\s+date|accumulated|akkumulert)\b",
            re.IGNORECASE,
        ),
        # Analytics patterns
        "analytics_location_trend": re.compile(
            r"\b(how(?:'s|s)?\s+\w+\s+(?:doing|performing|trending)|location\s+trend|store\s+performance|butikk.{0,10}(?:g[åa]r|trend))\b",
            re.IGNORECASE,
        ),
        "analytics_mix_vs_fleet": re.compile(
            r"\b(mix\s+(?:vs|versus|compared|mot)\s+fleet|product\s+mix.{0,15}fleet|group\s+mix|category\s+share\s+vs)\b",
            re.IGNORECASE,
        ),
        "analytics_fleet_ranking": re.compile(
            r"\b(best.{0,5}(?:store|worst|performing)|worst.{0,5}(?:store|performing)|rank(?:ing)?\s+(?:store|location)|top.{0,5}(?:store|location)|bottom.{0,5}(?:store|location))\b",
            re.IGNORECASE,
        ),
        "analytics_labor_efficiency": re.compile(
            r"\b(labor\s+efficiency|labour\s+efficiency|most\s+efficient\s+store|labor\s+cost\s+(?:by|per)\s+(?:store|location)|overtime\s+(?:by|per)\s+(?:store|location))\b",
            re.IGNORECASE,
        ),
        "analytics_staffing": re.compile(
            r"\b(overstaffed|understaffed|staffing\s+(?:level|recommend|benchmark)|right\s+staff|too\s+many\s+staff|not\s+enough\s+staff)\b",
            re.IGNORECASE,
        ),
        "analytics_sick_leave": re.compile(
            r"\b(sick\s+leave|sykefrav[æe]r|egenmelding|sykemelding|absence\s+rate|frav[æe]rs?\s*(?:prosent|rate|%))\b",
            re.IGNORECASE,
        ),
    }
    for key, regex in trigger_map.items():
        _PATTERN_TRIGGERS.append((regex, key))


# ---------------------------------------------------------------------------
# Startup: load CTXE YAML files
# ---------------------------------------------------------------------------

def _find_ctxe_dir() -> Path:
    """Find the CTXE directory relative to the project root."""
    # Walk up from this file to find the project root (where CTXE/ lives)
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "CTXE"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("Cannot find CTXE/ directory")


def _load_yaml(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _render_duckdb_syntax(data: dict) -> str:
    """Render duckdb_syntax_short.yaml to compact text."""
    lines = ["DUCKDB SYNTAX:"]
    for section, items in data.items():
        if section == "gotchas":
            for g in items:
                lines.append(f"  ! {g}")
        elif isinstance(items, dict):
            for key, val in items.items():
                if isinstance(val, str):
                    # Single-line
                    lines.append(f"  {key}: {val.strip()}")
                else:
                    lines.append(f"  {key}: {val}")
        elif isinstance(items, list):
            for item in items:
                lines.append(f"  - {item}")
    return "\n".join(lines)


def init_context():
    """Load all CTXE YAML artifacts. Call once at startup."""
    global _tables, _global_rules, _join_recipes, _patterns
    global _duckdb_syntax, _taxonomy_prompt, _loaded

    ctxe = _find_ctxe_dir()

    # --- schema_metadata.yaml ---
    schema_data = _load_yaml(ctxe / "schema_metadata.yaml")
    _tables.clear()
    _global_rules.clear()
    _join_recipes.clear()

    for key, val in schema_data.items():
        if key == "global_rules":
            _global_rules = val
        elif key == "join_recipes":
            _join_recipes = val
        elif isinstance(val, dict) and "domain" in val:
            _tables[key] = val

    # --- patterns.yaml ---
    patterns_data = _load_yaml(ctxe / "patterns.yaml")
    _patterns.clear()
    for key, val in patterns_data.items():
        if isinstance(val, dict) and "sql" in val:
            _patterns[key] = val

    # --- duckdb_syntax_short.yaml ---
    syntax_data = _load_yaml(ctxe / "duckdb_syntax_short.yaml")
    _duckdb_syntax = _render_duckdb_syntax(syntax_data)

    # --- product_taxonomy.yaml ---
    taxonomy_data = _load_yaml(ctxe / "product_taxonomy.yaml")
    _taxonomy_prompt = taxonomy_data.get("taxonomy_for_prompt", "")

    # Build pattern triggers
    _build_pattern_triggers()

    _loaded = True
    table_count = len(_tables)
    pattern_count = len(_patterns)
    print(f"CTXE context loaded: {table_count} tables, {pattern_count} patterns")


# ---------------------------------------------------------------------------
# Per-request: assemble context
# ---------------------------------------------------------------------------

def _detect_domains(question: str) -> set[str]:
    """Detect which data domains the question touches."""
    domains = set()
    for domain, regex in _DOMAIN_RES:
        if regex.search(question):
            domains.add(domain)

    # Labor always implies locations (need department_mapping bridge)
    if "labor" in domains:
        domains.add("locations")

    # Waste with location implies we need the terminal->installation path
    if "waste" in domains:
        domains.add("locations")

    # If no domain detected, default to sales + locations (most common)
    if not domains:
        domains = {"sales", "locations"}

    return domains


def _has_raw_signals(question: str) -> bool:
    """Check if question needs raw transaction-level data."""
    return bool(_RAW_SIGNALS.search(question))


def _select_tables(domains: set[str], use_analytics: bool = True) -> dict[str, dict]:
    """Filter tables by detected domains, skip excluded/empty.

    When use_analytics=True and analytics domain is detected,
    suppress raw equivalents that analytics tables replace.
    """
    # Determine which raw tables to suppress
    suppress = set()
    if use_analytics and "analytics" in domains:
        suppress = _ANALYTICS_SUPPRESSES.get("analytics", set())

    selected = {}
    for name, meta in _tables.items():
        if meta.get("exclude_from_llm"):
            continue
        if meta.get("row_count", 0) == 0:
            continue
        table_domain = meta.get("domain", "")
        if table_domain in domains:
            # Suppress raw tables when analytics is active
            if name in suppress:
                continue
            selected[name] = meta
    return selected


def _render_schema_block(tables: dict[str, dict]) -> str:
    """Render selected tables as compact schema text."""
    lines = ["SCHEMA (filtered to relevant tables):"]
    for name, meta in tables.items():
        desc = meta.get("description", "").strip().split("\n")[0]
        row_count = meta.get("row_count")
        row_str = f" ~{row_count:,} rows." if row_count else ""
        lines.append(f"\n{name} — {desc}{row_str}")

        # Columns
        columns = meta.get("columns", {})
        if columns:
            col_parts = []
            for col_name, col_meta in columns.items():
                if col_name.startswith("_"):
                    continue  # Skip internal columns
                ctype = col_meta.get("type", "?")
                # Shorten type names
                for long, short in [("INTEGER", "INT"), ("BIGINT", "INT"), ("VARCHAR", "STR"),
                                     ("BOOLEAN", "BOOL"), ("TIMESTAMPTZ", "TSTZ"),
                                     ("TIMESTAMP", "TS")]:
                    if ctype.upper().startswith(long):
                        ctype = short
                        break
                if ctype.startswith("DECIMAL"):
                    ctype = "DEC"
                col_parts.append(f"{col_name}:{ctype}")
            lines.append(f"  ({', '.join(col_parts)})")

        # Joins
        joins = meta.get("joins", {})
        for join_name, join_sql in joins.items():
            join_text = join_sql.strip().split("\n")[0] if "\n" not in join_sql else join_sql.strip().replace("\n", "\n    ")
            lines.append(f"  JOIN {join_name}: {join_text}")

        # Gotchas
        gotchas = meta.get("gotchas", [])
        for g in gotchas:
            lines.append(f"  ! {g}")

    return "\n".join(lines)


def _render_rules() -> str:
    """Render global rules as compact text."""
    lines = ["RULES:"]
    for key, text in _global_rules.items():
        lines.append(f"- {key}: {text.strip()}")
    return "\n".join(lines)


def _select_recipes(domains: set[str]) -> str:
    """Select join recipes matching detected domains."""
    selected = []
    for key, recipe in _join_recipes.items():
        recipe_domains = set(recipe.get("domains", []))
        if recipe_domains & domains == recipe_domains:
            desc = recipe.get("description", key)
            sql = recipe.get("sql", "").strip()
            selected.append(f"\nJOIN RECIPE — {desc}:\n{sql}")
    if not selected:
        return ""
    return "\n".join(selected)


def _match_patterns(question: str) -> str:
    """Match question to 0-2 few-shot SQL examples."""
    matched = []
    for regex, pattern_key in _PATTERN_TRIGGERS:
        if regex.search(question) and pattern_key in _patterns:
            matched.append(pattern_key)
        if len(matched) >= 2:
            break

    if not matched:
        return ""

    lines = []
    for key in matched:
        p = _patterns[key]
        lines.append(f'\nFEW-SHOT EXAMPLE:')
        lines.append(f'Example: "{p.get("question", "")}"')
        notes = p.get("notes", "").strip()
        if notes:
            lines.append(f"Notes: {notes}")
        sql = p.get("sql", "").strip()
        lines.append(f"SQL:\n{sql}")

    return "\n".join(lines)


def assemble_context(question: str, force_raw: bool = False, mentions: list[dict] | None = None) -> str:
    """Build the per-question LLM context from CTXE artifacts.

    Args:
        question: The user's natural language question.
        force_raw: If True, skip analytics routing (for SQL retry fallback).
        mentions: Pre-resolved entities from mention UI [{type, id, label}, ...].
                  When provided, these bypass fuzzy resolution for the given entity types.

    Returns a string to inject into the system prompt.
    """
    if not _loaded:
        raise RuntimeError("Context not initialized — call init_context() first")

    # 1. Domain detection
    domains = _detect_domains(question)

    # 1b. Entity resolution — resolve location aliases
    # If mentions include locations, use those instead of fuzzy-resolving
    mention_location_ids = {m["id"] for m in (mentions or []) if m.get("type") == "location"}
    if mention_location_ids:
        from app.context.entity_resolver import _location_index, LocationMatch
        location_matches = []
        for ruid in mention_location_ids:
            loc = _location_index.get_entity(ruid)
            if loc:
                location_matches.append(LocationMatch(
                    revenue_unit_id=ruid,
                    db_name=loc["db_name"],
                    display_name=loc["display_name"],
                    customer_id=loc["customer_id"],
                    brand=loc["brand"],
                    status=loc["status"],
                    merged_into_ruid=loc["merged_into_ruid"],
                    alias_matched=loc["display_name"],
                ))
        # Ensure locations domain is active when mentions reference locations
        domains.add("locations")
    else:
        location_matches = resolve_locations(question)
    location_hints_block = format_location_hints(location_matches)

    # 1c. Entity resolution — resolve product aliases
    mention_product_ids = {m["id"] for m in (mentions or []) if m.get("type") == "product"}
    if mention_product_ids:
        from app.context.entity_resolver import _product_index, ProductMatch
        product_matches = []
        for pid in mention_product_ids:
            prod = _product_index.get_entity(pid)
            if prod:
                product_matches.append(ProductMatch(
                    product_name=prod["product_name"],
                    description=prod["description"],
                    category=prod.get("category"),
                    alias_matched=prod["product_name"],
                ))
        domains.add("products")
    else:
        product_matches = resolve_products(question)
    product_hints_block = format_product_hints(product_matches)

    # 2. Smart analytics routing
    # Use analytics tables unless raw signals detected or force_raw
    use_analytics = (
        "analytics" in domains
        and not force_raw
        and not _has_raw_signals(question)
    )

    # 3. Table selection
    tables = _select_tables(domains, use_analytics=use_analytics)

    # 4. Schema block
    schema_block = _render_schema_block(tables)

    # 5. Global rules (always included)
    rules_block = _render_rules()

    # 5. Join recipes (matching domains)
    recipes_block = _select_recipes(domains)

    # 6. DuckDB syntax (always included)
    syntax_block = _duckdb_syntax

    # 7. Product taxonomy (always included)
    taxonomy_block = _taxonomy_prompt.strip()

    # 8. Pattern matching (0-2 few-shot examples)
    patterns_block = _match_patterns(question)

    # 9. Data dictionary from schema.py runtime data
    from app.schema import get_data_dictionary
    data_dict = get_data_dictionary()

    # Assemble
    parts = [schema_block]
    if location_hints_block:
        parts.append(location_hints_block)
    if product_hints_block:
        parts.append(product_hints_block)
    parts.append(rules_block)
    if recipes_block:
        parts.append(recipes_block)
    parts.append(syntax_block)
    if taxonomy_block:
        parts.append(taxonomy_block)
    if patterns_block:
        parts.append(patterns_block)
    if data_dict:
        parts.append(data_dict)

    return "\n\n".join(parts)
