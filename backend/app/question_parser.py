"""
Extract structured entities from natural language questions.

Zero-cost (no LLM, no DB) — just string matching against the product catalog
stems and regex for time period detection.
"""

import re

_product_stems: set[str] = set()
_location_names: list[str] = []  # Full location names from munu.installations

# Minimum stem length to avoid false positives (e.g. "is", "og")
_MIN_STEM_LEN = 4


def set_product_stems(stems: list[str]) -> None:
    """Called at startup with stems from the product catalog."""
    global _product_stems
    _product_stems = {s.lower() for s in stems if len(s) >= _MIN_STEM_LEN}
    print(f"Question parser: loaded {len(_product_stems)} product stems")


def set_location_names(names: list[str]) -> None:
    """Called at startup with location names from munu.installations."""
    global _location_names
    _location_names = [n for n in names if n and len(n) > 2]
    print(f"Question parser: loaded {len(_location_names)} location names")


# Time period patterns: (compiled regex, canonical label)
# Order matters — longer/more specific patterns first to avoid partial matches
_TIME_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bforrige\s+måned\b", re.IGNORECASE), "last_month"),
    (re.compile(r"\blast\s+month\b", re.IGNORECASE), "last_month"),
    (re.compile(r"\bdenne\s+måneden\b", re.IGNORECASE), "this_month"),
    (re.compile(r"\bthis\s+month\b", re.IGNORECASE), "this_month"),
    (re.compile(r"\bforrige\s+uke\b", re.IGNORECASE), "last_week"),
    (re.compile(r"\blast\s+week\b", re.IGNORECASE), "last_week"),
    (re.compile(r"\bdenne\s+uka\b", re.IGNORECASE), "this_week"),
    (re.compile(r"\bdenne\s+uken\b", re.IGNORECASE), "this_week"),
    (re.compile(r"\bthis\s+week\b", re.IGNORECASE), "this_week"),
    (re.compile(r"\bi\s+går\b", re.IGNORECASE), "yesterday"),
    (re.compile(r"\bigår\b", re.IGNORECASE), "yesterday"),
    (re.compile(r"\byesterday\b", re.IGNORECASE), "yesterday"),
    (re.compile(r"\bi\s+dag\b", re.IGNORECASE), "today"),
    (re.compile(r"\btoday\b", re.IGNORECASE), "today"),
    (re.compile(r"\bi\s+fjor\b", re.IGNORECASE), "last_year"),
    (re.compile(r"\blast\s+year\b", re.IGNORECASE), "last_year"),
    (re.compile(r"\bi\s+år\b", re.IGNORECASE), "this_year"),
    (re.compile(r"\bthis\s+year\b", re.IGNORECASE), "this_year"),
]


def parse_question(question: str) -> dict:
    """Extract structured entities from a natural language question.

    Returns:
        {
            "matched_products": [...],  # list of matched product stem strings
            "time_period": "...",       # e.g. "today", "yesterday", or None
        }
    """
    q_lower = question.lower()

    # Product matching: check which stems appear at word boundaries in the question
    # This avoids false positives like "this month" matching stem "is mo"
    matched = []
    for stem in _product_stems:
        # Stem must start at a word boundary (start of string or after space/punctuation)
        idx = q_lower.find(stem)
        if idx == -1:
            continue
        if idx == 0 or not q_lower[idx - 1].isalpha():
            matched.append(stem)

    # Time period: first match wins
    time_period = None
    for pattern, label in _TIME_PATTERNS:
        if pattern.search(question):
            time_period = label
            break

    # Location matching: check if any known location name appears in the question
    matched_locations = []
    for loc_name in _location_names:
        # Match on the distinctive part (e.g. "Kvadrat" from "Kanelsnurren Kvadrat")
        # Check both full name and last word(s) after brand prefix
        if loc_name.lower() in q_lower:
            matched_locations.append(loc_name)
            continue
        # Try matching the location suffix (after "Kanelsnurren ", "Steam ", "Mjøl " etc.)
        parts = loc_name.split(maxsplit=1)
        if len(parts) == 2 and len(parts[1]) >= 4 and parts[1].lower() in q_lower:
            matched_locations.append(loc_name)

    return {
        "matched_products": sorted(matched),
        "matched_locations": matched_locations,
        "time_period": time_period,
    }


# ---- Query hints: pre-model smart parsing ----
# Detect intent from the question and build concrete SQL hints for the LLM.

_SALES_RE = re.compile(
    r"\b(sol[gd]t|sell|sold|sale[s]?|salg|kj[øo]p|bought|order|bestill|antall|quantity|how\s+many)\b",
    re.IGNORECASE,
)
_LOCATION_RE = re.compile(
    r"\b(location|lokasjoner?|butik[k]?|outlet|sted|avdeling|installation|per\s+sted|by\s+location)\b",
    re.IGNORECASE,
)
_REVENUE_RE = re.compile(
    r"\b(revenue|omsetning|inntekt|turnover|income|earnings)\b",
    re.IGNORECASE,
)
_CATEGORY_RE = re.compile(
    r"\b(categor(?:y|ies)|kategori(?:er)?|group|gruppe)\b",
    re.IGNORECASE,
)
_PAYMENT_RE = re.compile(
    r"\b(payment|betaling|vipps|kort|cash|kontant)\b",
    re.IGNORECASE,
)
_WASTE_RE = re.compile(
    r"\b(waste|svinn|kast(?:et)?|thrown\s+away)\b",
    re.IGNORECASE,
)
_LABOR_RE = re.compile(
    r"\b(shift|skift|vakt|arbeid|timer|hours?\s+worked|labor|labour)\b",
    re.IGNORECASE,
)

_DATE_HINTS = {
    "today": "o.order_date = CURRENT_DATE",
    "yesterday": "o.order_date = CURRENT_DATE - INTERVAL '1 day'",
    "this_week": "o.order_date >= DATE_TRUNC('week', CURRENT_DATE)",
    "last_week": "o.order_date >= DATE_TRUNC('week', CURRENT_DATE) - INTERVAL '7 days' AND o.order_date < DATE_TRUNC('week', CURRENT_DATE)",
    "this_month": "o.order_date >= DATE_TRUNC('month', CURRENT_DATE)",
    "last_month": "o.order_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' AND o.order_date < DATE_TRUNC('month', CURRENT_DATE)",
    "this_year": "o.order_date >= DATE_TRUNC('year', CURRENT_DATE)",
    "last_year": "o.order_date >= DATE_TRUNC('year', CURRENT_DATE) - INTERVAL '1 year' AND o.order_date < DATE_TRUNC('year', CURRENT_DATE)",
}


def build_query_hints(question: str) -> str:
    """Build SQL hints from question content to guide the LLM."""
    parsed = parse_question(question)
    hints = []

    is_sales = bool(_SALES_RE.search(question))
    is_location = bool(_LOCATION_RE.search(question))
    is_revenue = bool(_REVENUE_RE.search(question))
    is_waste = bool(_WASTE_RE.search(question))
    is_labor = bool(_LABOR_RE.search(question))

    has_location_match = bool(parsed["matched_locations"])

    # Core sales/order data
    if is_sales or is_revenue or is_location or has_location_match or parsed["matched_products"]:
        hints.append(
            "Sales data: munu.order_lines ol "
            "JOIN munu.orders o ON ol.customer_id = o.customer_id AND ol.soid = o.soid"
        )

    # Location names (revenue_units, NOT installations — orders.inid is always empty)
    if is_location or has_location_match:
        hints.append(
            "Location names: JOIN munu.revenue_units ru "
            "ON o.customer_id = ru.customer_id AND o.revenue_unit_id = ru.revenue_unit_id — use ru.name for location"
        )

    # Specific location filter
    for loc in parsed["matched_locations"]:
        hints.append(f"Location filter: ru.name = '{loc}'")
        break  # Only use the first match to avoid conflicting filters

    # Product matching
    for stem in parsed["matched_products"]:
        hints.append(f"Product filter: ol.article_name ILIKE '%{stem}%'")

    # Revenue
    if is_revenue:
        hints.append("Revenue: SUM(ol.net_amount) or o.total_amount")

    # Quantity
    if is_sales and not is_revenue:
        hints.append("Quantity: SUM(ol.quantity)")

    # Date filter
    if parsed["time_period"] and parsed["time_period"] in _DATE_HINTS:
        hints.append(f"Date filter: {_DATE_HINTS[parsed['time_period']]}")

    # Category
    if _CATEGORY_RE.search(question):
        hints.append(
            "Categories: JOIN munu.articles a ON ol.article_id = a.article_id "
            "AND ol.customer_id = a.customer_id — use a.article_group_name"
        )

    # Payment
    if _PAYMENT_RE.search(question):
        hints.append(
            "Payments: munu.order_payments op "
            "JOIN munu.payment_types pt ON op.ptid = pt.ptid AND op.customer_id = pt.customer_id"
        )

    # Waste
    if is_waste:
        hints.append("Waste data: munu.article_waste — has article_name, quantity, total_cost, reason")

    # Labor
    if is_labor:
        hints.append("Labor: munu.labor_shifts or planday.punchclock_shifts")

    if not hints:
        return ""

    return "\n\nQUERY HINTS (use these tables and joins):\n" + "\n".join(f"- {h}" for h in hints)
