"""
Entity Resolver — maps user entity names to correct IDs/filters.

Generic EntityIndex engine (n-gram matching) used for both locations and products.
Loads aliases from CTXE/lookups.yaml at startup, builds in-memory indexes.
Per-question: tokenize -> exact match -> prefix fallback -> format hints.

Zero DB cost, ~60 aliases, <1ms per query.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Shared utility
# ---------------------------------------------------------------------------

def _generate_ngrams(text: str, max_n: int = 3) -> list[str]:
    """Generate 1-grams, 2-grams, 3-grams from lowercased, cleaned text."""
    cleaned = re.sub(r"[^\w\s-]", "", text.lower())
    words = cleaned.split()
    ngrams = []
    for n in range(1, min(max_n + 1, len(words) + 1)):
        for i in range(len(words) - n + 1):
            ngrams.append(" ".join(words[i:i + n]))
    return ngrams


# ---------------------------------------------------------------------------
# Generic EntityIndex
# ---------------------------------------------------------------------------

class EntityIndex:
    """Reusable n-gram matching engine for entity resolution.

    Usage:
        idx = EntityIndex("locations")
        idx.add_entity("366", {"db_name": "KS Sentrum", ...})
        idx.add_alias("verksgata", "366")
        matches = idx.resolve("sales at verksgata")  # [("366", "verksgata")]
    """

    def __init__(self, name: str, *, min_alias_len: int = 2, min_prefix_len: int = 5):
        self.name = name
        self.min_alias_len = min_alias_len
        self.min_prefix_len = min_prefix_len
        self._entities: dict[str, dict] = {}        # entity_id -> metadata
        self._alias_index: dict[str, str] = {}      # alias (lowercased) -> entity_id

    def add_entity(self, entity_id: str, metadata: dict) -> None:
        """Register entity with metadata (first wins for duplicate IDs)."""
        if entity_id not in self._entities:
            self._entities[entity_id] = metadata

    def add_alias(self, alias: str, entity_id: str) -> None:
        """Register lowercased alias -> entity_id (first wins, skip if too short)."""
        alias = alias.strip().lower()
        if len(alias) < self.min_alias_len:
            return
        if alias not in self._alias_index:
            self._alias_index[alias] = entity_id

    def resolve(self, question: str) -> list[tuple[str, str]]:
        """Resolve entity references in question text.

        Returns list of (entity_id, matched_alias) pairs, deduped by entity_id.
        Tries exact match (longer n-grams first), then prefix fallback.
        """
        ngrams = _generate_ngrams(question)
        matched: dict[str, str] = {}  # entity_id -> alias

        # Exact matches (longer n-grams first for precision)
        for ngram in reversed(ngrams):
            if ngram in self._alias_index:
                eid = self._alias_index[ngram]
                if eid not in matched:
                    matched[eid] = ngram

        # Prefix fallback (only if no exact matches found)
        if not matched:
            for ngram in ngrams:
                if len(ngram) < self.min_prefix_len:
                    continue
                for alias, eid in self._alias_index.items():
                    if len(alias) < self.min_prefix_len:
                        continue
                    if alias.startswith(ngram) or ngram.startswith(alias):
                        if eid not in matched:
                            matched[eid] = ngram
                        break

        return list(matched.items())

    def get_entity(self, entity_id: str) -> dict | None:
        return self._entities.get(entity_id)

    def get_all_entities(self) -> dict[str, dict]:
        return self._entities

    def get_aliases_for_id(self, entity_id: str) -> list[str]:
        return [a for a, eid in self._alias_index.items() if eid == entity_id]

    @property
    def alias_count(self) -> int:
        return len(self._alias_index)

    @property
    def entity_count(self) -> int:
        return len(self._entities)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class LocationMatch:
    revenue_unit_id: str
    db_name: str            # munu.revenue_units.name (POS name)
    display_name: str       # Human-friendly display name
    customer_id: int | None
    brand: str | None
    status: str             # active / closed / merged / inactive
    merged_into_ruid: str | None
    alias_matched: str      # The alias string that triggered the match


@dataclass
class ProductMatch:
    product_name: str       # Normalized name for SQL ILIKE
    description: str        # Category path + description from lookups.yaml
    category: str | None    # Category name (if available)
    alias_matched: str      # The alias that triggered the match


# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------

_location_index = EntityIndex("locations")
_product_index = EntityIndex("products", min_alias_len=3)
_location_loaded = False
_product_loaded = False

# Brand prefixes to strip when generating auto-aliases
_BRAND_PREFIXES = ("BB ", "KS ", "Steam ", "Mjol ", "Mjol ")


# ---------------------------------------------------------------------------
# Startup: find CTXE dir
# ---------------------------------------------------------------------------

def _find_ctxe_dir() -> Path:
    """Find the CTXE directory relative to the project root."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "CTXE"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("Cannot find CTXE/ directory")


# ---------------------------------------------------------------------------
# Location index
# ---------------------------------------------------------------------------

def init_location_index() -> None:
    """Load CTXE/lookups.yaml and build the in-memory location alias index."""
    global _location_index, _location_loaded

    _location_index = EntityIndex("locations")

    ctxe = _find_ctxe_dir()
    path = ctxe / "lookups.yaml"
    if not path.exists():
        print("Entity resolver: lookups.yaml not found, skipping")
        return

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    locations = data.get("locations", {})
    aliases_section = data.get("aliases", {}).get("locations", {})

    # Customer ID mapping
    region_customer = {
        "oslo": 10352,
        "stavanger": 761,
    }

    # --- Phase 1: Parse all locations and build entities ---
    for region, entries in locations.items():
        if region in ("planday_non_store", "brands"):
            continue
        if not isinstance(entries, list):
            continue

        customer_id = region_customer.get(region)
        for loc in entries:
            if not isinstance(loc, dict):
                continue
            ruid = str(loc.get("ruid", ""))
            if not ruid:
                continue

            name = loc.get("name", "")
            display = loc.get("display", name)
            brand = loc.get("brand")
            status = loc.get("status", "active")
            merged_into = loc.get("merged_into")
            planday_dept = loc.get("planday_dept", "")

            # Store metadata (first entry wins for duplicate ruids)
            _location_index.add_entity(ruid, {
                "ruid": ruid,
                "db_name": name,
                "display_name": display,
                "customer_id": customer_id,
                "brand": brand,
                "status": status,
                "merged_into_ruid": str(merged_into) if merged_into else None,
                "planday_dept": planday_dept,
                "region": region,
            })

            # Auto-generate aliases from location metadata
            # 1. Display name + suffix without brand prefix
            if display:
                _location_index.add_alias(display, ruid)
                for prefix in _BRAND_PREFIXES:
                    if display.startswith(prefix):
                        _location_index.add_alias(display[len(prefix):], ruid)
                        break

            # 2. DB name + suffix without brand prefix
            if name:
                _location_index.add_alias(name, ruid)
                for prefix in _BRAND_PREFIXES:
                    if name.startswith(prefix):
                        rest = name[len(prefix):]
                        _location_index.add_alias(rest, ruid)
                        # Also add after removing "Kanelsnurren " from rest
                        if rest.startswith("Kanelsnurren "):
                            _location_index.add_alias(rest[len("Kanelsnurren "):], ruid)
                        break

            # 3. Planday department name
            if planday_dept:
                _location_index.add_alias(planday_dept, ruid)

    # --- Phase 2: Parse explicit aliases section ---
    for alias_str, alias_data in aliases_section.items():
        if isinstance(alias_data, dict):
            ruid = str(alias_data.get("ruid", ""))
        else:
            ruid = str(alias_data)
        if ruid:
            _location_index.add_alias(alias_str, ruid)

    _location_loaded = True
    print(f"Entity resolver: loaded {_location_index.alias_count} location aliases, "
          f"{_location_index.entity_count} unique locations")


def resolve_locations(question: str) -> list[LocationMatch]:
    """Resolve location references in a question to LocationMatch objects."""
    if not _location_loaded:
        return []

    results = []
    for ruid, alias in _location_index.resolve(question):
        loc = _location_index.get_entity(ruid)
        if not loc:
            continue
        results.append(LocationMatch(
            revenue_unit_id=ruid,
            db_name=loc["db_name"],
            display_name=loc["display_name"],
            customer_id=loc["customer_id"],
            brand=loc["brand"],
            status=loc["status"],
            merged_into_ruid=loc["merged_into_ruid"],
            alias_matched=alias,
        ))

    return results


def format_location_hints(matches: list[LocationMatch]) -> str:
    """Format resolved locations as a prompt block for the LLM."""
    if not matches:
        return ""

    lines = ["RESOLVED LOCATIONS (use these exact filters):"]
    for m in matches:
        lines.append(
            f'- "{m.alias_matched}" = ru.name = \'{m.db_name}\' '
            f'(revenue_unit_id = \'{m.revenue_unit_id}\', display: {m.display_name})'
        )
        lines.append(
            f"  Use: WHERE o.revenue_unit_id = '{m.revenue_unit_id}' "
            f"AND o.customer_id = {m.customer_id}"
        )
        if m.status == "merged" and m.merged_into_ruid:
            merged = _location_index.get_entity(m.merged_into_ruid) or {}
            lines.append(
                f"  Note: Merged into {merged.get('db_name', '?')} "
                f"(ruid {m.merged_into_ruid}). Include both for historical data."
            )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Product index
# ---------------------------------------------------------------------------

def init_product_index() -> None:
    """Load CTXE/lookups.yaml and build the in-memory product alias index."""
    global _product_index, _product_loaded

    _product_index = EntityIndex("products", min_alias_len=3)

    ctxe = _find_ctxe_dir()
    path = ctxe / "lookups.yaml"
    if not path.exists():
        print("Entity resolver: lookups.yaml not found, skipping products")
        return

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # --- Product aliases (e.g. "kanelsnurr" -> "Boller -- cinnamon bun") ---
    product_aliases = data.get("aliases", {}).get("products", {})
    for alias_str, desc in product_aliases.items():
        # Entity ID = the alias itself (normalized for ILIKE)
        product_name = alias_str.strip()
        # Parse category from description (format: "Category > Sub" or "Category -- desc")
        category = None
        if isinstance(desc, str):
            # "Boller \u2014 cinnamon bun" or "Varm drikke > Kaffedrikker"
            cat_part = desc.split("\u2014")[0].split(">")[0].strip()
            if cat_part:
                category = cat_part

        _product_index.add_entity(product_name, {
            "product_name": product_name,
            "description": desc if isinstance(desc, str) else "",
            "category": category,
        })
        _product_index.add_alias(alias_str, product_name)

    # --- Top products (by revenue) ---
    top_products = data.get("top_products", {})
    for region, products in top_products.items():
        if not isinstance(products, list):
            continue
        for prod in products:
            if not isinstance(prod, dict):
                continue
            name = prod.get("name", "").strip()
            if not name:
                continue
            category = prod.get("category", "")
            revenue = prod.get("revenue_mnok", 0)

            entity_id = name.lower()
            # Only add if not already registered (alias section takes priority)
            if not _product_index.get_entity(entity_id):
                desc = f"{category} -- {name}"
                if revenue:
                    desc += f" ({revenue}M NOK)"
                _product_index.add_entity(entity_id, {
                    "product_name": name,
                    "description": desc,
                    "category": category,
                })
            _product_index.add_alias(name, entity_id)

    _product_loaded = True
    print(f"Entity resolver: loaded {_product_index.alias_count} product aliases, "
          f"{_product_index.entity_count} unique products")


def resolve_products(question: str) -> list[ProductMatch]:
    """Resolve product references in a question to ProductMatch objects."""
    if not _product_loaded:
        return []

    results = []
    for entity_id, alias in _product_index.resolve(question):
        prod = _product_index.get_entity(entity_id)
        if not prod:
            continue
        results.append(ProductMatch(
            product_name=prod["product_name"],
            description=prod["description"],
            category=prod.get("category"),
            alias_matched=alias,
        ))

    return results


def format_product_hints(matches: list[ProductMatch]) -> str:
    """Format resolved products as a prompt block for the LLM."""
    if not matches:
        return ""

    lines = ["RESOLVED PRODUCTS (use these exact filters):"]
    for m in matches:
        cat_info = f" category: {m.category}" if m.category else ""
        lines.append(f'- "{m.alias_matched}" ->{cat_info}')
        lines.append(f"  Use: ol.article_name ILIKE '%{m.product_name}%'")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Data access for other modules
# ---------------------------------------------------------------------------

def get_locations_by_ruid() -> dict[str, dict]:
    """Return location metadata indexed by ruid (for schema.py data dictionary)."""
    return _location_index.get_all_entities()


def get_location_data_for_parser() -> list[dict]:
    """Return location data in format suitable for question_parser.set_location_names()."""
    result = []
    for ruid, loc in _location_index.get_all_entities().items():
        aliases = _location_index.get_aliases_for_id(ruid)
        result.append({
            "name": loc["db_name"],
            "display_name": loc["display_name"],
            "ruid": ruid,
            "customer_id": loc["customer_id"],
            "aliases": aliases,
        })
    return result
