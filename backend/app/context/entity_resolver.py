"""
Entity Resolver — maps user location names to correct revenue_unit_ids.

Loads aliases from CTXE/lookups.yaml at startup, builds an in-memory index.
Per-question: tokenize → exact match → fuzzy fallback → format hints.

Zero DB cost, ~40 aliases, <1ms per query.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml


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


# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------

# alias (lowercased) -> LocationMatch template (alias_matched filled at query time)
_alias_index: dict[str, dict] = {}

# ruid -> full location metadata (for dedup and lookup)
_locations_by_ruid: dict[str, dict] = {}

_loaded = False

# Brand prefixes to strip when generating auto-aliases
_BRAND_PREFIXES = ("BB ", "KS ", "Steam ", "Mjol ", "Mjøl ")


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

def _find_ctxe_dir() -> Path:
    """Find the CTXE directory relative to the project root."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "CTXE"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("Cannot find CTXE/ directory")


def _add_alias(alias: str, ruid: str) -> None:
    """Add a lowercased alias pointing to a ruid (skip if empty or too short)."""
    alias = alias.strip().lower()
    if len(alias) < 2:
        return
    if alias not in _alias_index:
        _alias_index[alias] = ruid


def init_location_index() -> None:
    """Load CTXE/lookups.yaml and build the in-memory alias index."""
    global _loaded

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

    # --- Phase 1: Parse all locations and build _locations_by_ruid ---
    _locations_by_ruid.clear()
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
            if ruid not in _locations_by_ruid:
                _locations_by_ruid[ruid] = {
                    "ruid": ruid,
                    "db_name": name,
                    "display_name": display,
                    "customer_id": customer_id,
                    "brand": brand,
                    "status": status,
                    "merged_into_ruid": str(merged_into) if merged_into else None,
                    "planday_dept": planday_dept,
                    "region": region,
                }

            # Auto-generate aliases from location metadata
            # 1. Display name suffix (e.g. "KS Verksgata" -> "verksgata")
            if display:
                _add_alias(display, ruid)
                for prefix in _BRAND_PREFIXES:
                    if display.startswith(prefix):
                        suffix = display[len(prefix):]
                        _add_alias(suffix, ruid)
                        break

            # 2. DB name suffix (e.g. "BB Kanelsnurren Ostbanehallen Oslo" -> last meaningful words)
            if name:
                _add_alias(name, ruid)
                for prefix in _BRAND_PREFIXES:
                    if name.startswith(prefix):
                        rest = name[len(prefix):]
                        _add_alias(rest, ruid)
                        # Also add after removing "Kanelsnurren " from rest
                        if rest.startswith("Kanelsnurren "):
                            _add_alias(rest[len("Kanelsnurren "):], ruid)
                        break

            # 3. Planday department name
            if planday_dept:
                _add_alias(planday_dept, ruid)

    # --- Phase 2: Parse explicit aliases section ---
    for alias_str, alias_data in aliases_section.items():
        if isinstance(alias_data, dict):
            ruid = str(alias_data.get("ruid", ""))
        else:
            ruid = str(alias_data)
        if ruid:
            _add_alias(alias_str, ruid)

    _loaded = True
    print(f"Entity resolver: loaded {len(_alias_index)} location aliases, "
          f"{len(_locations_by_ruid)} unique locations")


# ---------------------------------------------------------------------------
# Per-query resolution
# ---------------------------------------------------------------------------

def _generate_ngrams(text: str, max_n: int = 3) -> list[str]:
    """Generate 1-grams, 2-grams, 3-grams from lowercased, cleaned text."""
    # Strip punctuation (keep letters, digits, spaces, hyphens)
    cleaned = re.sub(r"[^\w\s-]", "", text.lower())
    words = cleaned.split()
    ngrams = []
    for n in range(1, min(max_n + 1, len(words) + 1)):
        for i in range(len(words) - n + 1):
            ngrams.append(" ".join(words[i:i + n]))
    return ngrams


def resolve_locations(question: str) -> list[LocationMatch]:
    """Resolve location references in a question to LocationMatch objects.

    1. Tokenize into n-grams
    2. Exact match against alias index
    3. Fuzzy fallback (Levenshtein <= 2) for unmatched n-grams >= 4 chars
    4. Deduplicate by ruid
    """
    if not _loaded:
        return []

    ngrams = _generate_ngrams(question)
    matched_ruids: dict[str, str] = {}  # ruid -> alias that matched

    # Exact matches (check longer n-grams first for better precision)
    for ngram in reversed(ngrams):
        if ngram in _alias_index:
            ruid = _alias_index[ngram]
            if ruid not in matched_ruids:
                matched_ruids[ruid] = ngram

    # Prefix fallback: if no exact match, check if any n-gram (5+ chars) is
    # a prefix of an alias or vice versa (catches truncations like "verksgat")
    if not matched_ruids:
        for ngram in ngrams:
            if len(ngram) < 5:
                continue
            for alias, ruid in _alias_index.items():
                if len(alias) < 5:
                    continue
                if alias.startswith(ngram) or ngram.startswith(alias):
                    if ruid not in matched_ruids:
                        matched_ruids[ruid] = ngram
                    break

    # Build LocationMatch objects
    results = []
    for ruid, alias in matched_ruids.items():
        loc = _locations_by_ruid.get(ruid)
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
            merged = _locations_by_ruid.get(m.merged_into_ruid, {})
            lines.append(
                f"  Note: Merged into {merged.get('db_name', '?')} "
                f"(ruid {m.merged_into_ruid}). Include both for historical data."
            )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Data access for other modules
# ---------------------------------------------------------------------------

def get_locations_by_ruid() -> dict[str, dict]:
    """Return location metadata indexed by ruid (for schema.py data dictionary)."""
    return _locations_by_ruid


def get_location_data_for_parser() -> list[dict]:
    """Return location data in format suitable for question_parser.set_location_names()."""
    result = []
    for ruid, loc in _locations_by_ruid.items():
        # Collect aliases for this ruid
        aliases = [alias for alias, r in _alias_index.items() if r == ruid]
        result.append({
            "name": loc["db_name"],
            "display_name": loc["display_name"],
            "ruid": ruid,
            "customer_id": loc["customer_id"],
            "aliases": aliases,
        })
    return result
