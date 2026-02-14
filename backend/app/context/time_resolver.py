"""
Time Resolver — detects time periods, comparison intent, and generates
SQL hints for the LLM.

Three detection layers (most specific first):
  1. "Same X" patterns  — "same day and time last week"
  2. Comparison prefix + base period — "sammenlignet med i går"
  3. Base period alone — "yesterday", "i dag"

Pure regex, no data loading, no DB cost, <1ms per query.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TimeResolution:
    time_period: str | None = None        # "today", "last_week", etc.
    comparison_period: str | None = None   # "same_day_last_week", etc.
    n_days: int | None = None             # for "last N days"
    matched_text: str | None = None       # the text that triggered the match


# ---------------------------------------------------------------------------
# Layer 1: Base time periods (EN + NO)
# ---------------------------------------------------------------------------

_BASE_PERIODS: list[tuple[str, re.Pattern]] = [
    # Order matters — more specific first
    ("today_sofar", re.compile(
        r"\b(so\s+far\s+today|hittil\s+i\s+dag|s[åa]\s+langt\s+i\s+dag)\b",
        re.IGNORECASE,
    )),
    ("today", re.compile(
        r"\b(today|i\s+dag)\b",
        re.IGNORECASE,
    )),
    ("yesterday", re.compile(
        r"\b(yesterday|ig[åa]r|i\s+g[åa]r)\b",
        re.IGNORECASE,
    )),
    ("ytd", re.compile(
        r"\b(year\s+to\s+date|YTD|hittil\s+i\s+[åa]r|s[åa]\s+langt\s+i\s+[åa]r)\b",
        re.IGNORECASE,
    )),
    ("ltm", re.compile(
        r"\b(last\s+twelve\s+months|LTM|trailing\s+12\s+months|"
        r"siste\s+(?:tolv|12)\s+m[åa]neder)\b",
        re.IGNORECASE,
    )),
    ("this_week", re.compile(
        r"\b(this\s+week|denne\s+uk(?:a|en))\b",
        re.IGNORECASE,
    )),
    ("last_week", re.compile(
        r"\b(last\s+week|forrige\s+uke|siste\s+uke(?:n)?)\b",
        re.IGNORECASE,
    )),
    ("this_weekend", re.compile(
        r"\b(this\s+weekend|i\s+helgen)\b",
        re.IGNORECASE,
    )),
    ("this_month", re.compile(
        r"\b(this\s+month|denne\s+m[åa]neden)\b",
        re.IGNORECASE,
    )),
    ("last_month", re.compile(
        r"\b(last\s+month|forrige\s+m[åa]ned|siste\s+m[åa]ned(?:en)?)\b",
        re.IGNORECASE,
    )),
    ("last_quarter", re.compile(
        r"\b(last\s+quarter|forrige\s+kvartal|siste\s+kvartal)\b",
        re.IGNORECASE,
    )),
    ("this_year", re.compile(
        r"\b(this\s+year|i\s+[åa]r)\b",
        re.IGNORECASE,
    )),
    ("last_year", re.compile(
        r"\b(last\s+year|i\s+fjor|forrige\s+[åa]r)\b",
        re.IGNORECASE,
    )),
]

# Dynamic "last N days" — must capture N
_LAST_N_DAYS_RE = re.compile(
    r"\b(?:last|past|siste|de\s+siste)\s+(\d+)\s+(?:days?|dager?|dagene)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Layer 2: Comparison prefix detection
# ---------------------------------------------------------------------------

_COMPARISON_PREFIX_RE = re.compile(
    r"\b(sammenlignet\s+med|i\s+forhold\s+til|opp?\s+mot|versus|vs\.?|kontra|"
    r"compared?\s+(?:to|with)|how\s+does\s+(?:that|this|it)\s+compare)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Layer 3: "Same X" patterns (most specific — checked first)
# ---------------------------------------------------------------------------

_SAME_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("same_time_last_week", re.compile(
        r"\b(same\s+(?:day\s+and\s+)?time\s+last\s+week|"
        r"samme\s+tid\s+forrige\s+uke)\b",
        re.IGNORECASE,
    )),
    ("same_day_last_week", re.compile(
        r"\b(same\s+(?:day|weekday)\s+last\s+week|"
        r"samme\s+(?:dag|ukedag)\s+forrige\s+uke)\b",
        re.IGNORECASE,
    )),
    ("same_day_last_year", re.compile(
        r"\b(same\s+(?:day|date)\s+last\s+year|"
        r"samme\s+(?:dag|dato)\s+i\s+fjor)\b",
        re.IGNORECASE,
    )),
    ("same_week_last_year", re.compile(
        r"\b(same\s+week\s+last\s+year|"
        r"(?:samme|tilsvarende)\s+uke\s+i\s+fjor)\b",
        re.IGNORECASE,
    )),
    ("same_week_two_years_ago", re.compile(
        r"\b(same\s+week\s+two\s+years?\s+ago|"
        r"samme\s+uke\s+for\s+to\s+[åa]r\s+siden)\b",
        re.IGNORECASE,
    )),
    ("same_month_last_year", re.compile(
        r"\b(same\s+month\s+last\s+year|"
        r"(?:samme|tilsvarende)\s+m[åa]ned\s+i\s+fjor)\b",
        re.IGNORECASE,
    )),
]


# ---------------------------------------------------------------------------
# SQL hint templates
# ---------------------------------------------------------------------------

_DATE_FILTERS: dict[str, str] = {
    "today":        "WHERE order_date = CURRENT_DATE",
    "today_sofar":  "WHERE order_date = CURRENT_DATE AND order_time <= CURRENT_TIME::TIME",
    "yesterday":    "WHERE order_date = CURRENT_DATE - INTERVAL '1 day'",
    "this_week":    "WHERE order_date >= DATE_TRUNC('week', CURRENT_DATE)",
    "last_week":    "WHERE order_date >= DATE_TRUNC('week', CURRENT_DATE) - INTERVAL '7 days' "
                    "AND order_date < DATE_TRUNC('week', CURRENT_DATE)",
    "this_weekend": "WHERE order_date >= DATE_TRUNC('week', CURRENT_DATE) + INTERVAL '5 days' "
                    "AND order_date <= DATE_TRUNC('week', CURRENT_DATE) + INTERVAL '6 days'",
    "this_month":   "WHERE order_date >= DATE_TRUNC('month', CURRENT_DATE)",
    "last_month":   "WHERE order_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' "
                    "AND order_date < DATE_TRUNC('month', CURRENT_DATE)",
    "last_quarter": "WHERE order_date >= DATE_TRUNC('quarter', CURRENT_DATE) - INTERVAL '3 months' "
                    "AND order_date < DATE_TRUNC('quarter', CURRENT_DATE)",
    "this_year":    "WHERE order_date >= DATE_TRUNC('year', CURRENT_DATE)",
    "last_year":    "WHERE YEAR(order_date) = YEAR(CURRENT_DATE) - 1",
    "ytd":          "WHERE order_date >= DATE_TRUNC('year', CURRENT_DATE) AND order_date <= CURRENT_DATE",
    "ltm":          "WHERE order_date >= CURRENT_DATE - INTERVAL '12 months'",
}

_COMPARISON_FILTERS: dict[str, dict[str, str]] = {
    "same_time_last_week": {
        "current": "WHERE order_date = CURRENT_DATE AND order_time <= CURRENT_TIME::TIME",
        "previous": "WHERE order_date = CURRENT_DATE - INTERVAL '7 days' AND order_time <= CURRENT_TIME::TIME",
        "note": "Both CTEs filter to same time-of-day. order_time is TIME, CURRENT_TIME is TIMETZ — cast with ::TIME.",
    },
    "same_day_last_week": {
        "current": "WHERE order_date = CURRENT_DATE",
        "previous": "WHERE order_date = CURRENT_DATE - INTERVAL '7 days'",
        "note": "Same weekday, one week apart.",
    },
    "same_day_last_year": {
        "current": "WHERE order_date = CURRENT_DATE",
        "previous": "WHERE order_date = CURRENT_DATE - INTERVAL '1 year'",
        "note": "Same calendar date last year.",
    },
    "same_week_last_year": {
        "current": "WHERE order_date >= DATE_TRUNC('week', CURRENT_DATE) "
                   "AND order_date < DATE_TRUNC('week', CURRENT_DATE) + INTERVAL '7 days'",
        "previous": "WHERE order_date >= DATE_TRUNC('week', CURRENT_DATE) - INTERVAL '1 year' "
                    "AND order_date < DATE_TRUNC('week', CURRENT_DATE) - INTERVAL '1 year' + INTERVAL '7 days'",
        "note": "Same ISO week, one year apart.",
    },
    "same_week_two_years_ago": {
        "current": "WHERE order_date >= DATE_TRUNC('week', CURRENT_DATE) "
                   "AND order_date < DATE_TRUNC('week', CURRENT_DATE) + INTERVAL '7 days'",
        "previous": "WHERE order_date >= DATE_TRUNC('week', CURRENT_DATE) - INTERVAL '2 years' "
                    "AND order_date < DATE_TRUNC('week', CURRENT_DATE) - INTERVAL '2 years' + INTERVAL '7 days'",
        "note": "Same ISO week, two years apart.",
    },
    "same_month_last_year": {
        "current": "WHERE order_date >= DATE_TRUNC('month', CURRENT_DATE) "
                   "AND order_date < DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month'",
        "previous": "WHERE order_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 year' "
                    "AND order_date < DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 year' + INTERVAL '1 month'",
        "note": "Same calendar month, one year apart.",
    },
    # Compositional comparisons (derived from prefix + base period)
    "vs_yesterday": {
        "current": "WHERE order_date = CURRENT_DATE",
        "previous": "WHERE order_date = CURRENT_DATE - INTERVAL '1 day'",
        "note": "Today vs yesterday.",
    },
    "vs_last_week": {
        "current": "WHERE order_date >= DATE_TRUNC('week', CURRENT_DATE)",
        "previous": "WHERE order_date >= DATE_TRUNC('week', CURRENT_DATE) - INTERVAL '7 days' "
                    "AND order_date < DATE_TRUNC('week', CURRENT_DATE)",
        "note": "This week vs last week.",
    },
    "vs_last_month": {
        "current": "WHERE order_date >= DATE_TRUNC('month', CURRENT_DATE)",
        "previous": "WHERE order_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' "
                    "AND order_date < DATE_TRUNC('month', CURRENT_DATE)",
        "note": "This month vs last month.",
    },
    "vs_last_year": {
        "current": "WHERE order_date >= DATE_TRUNC('year', CURRENT_DATE)",
        "previous": "WHERE YEAR(order_date) = YEAR(CURRENT_DATE) - 1",
        "note": "This year vs last year.",
    },
}

# Mapping from base period to compositional comparison label
_BASE_TO_COMPARISON: dict[str, str] = {
    "yesterday":    "vs_yesterday",
    "last_week":    "vs_last_week",
    "last_month":   "vs_last_month",
    "last_year":    "vs_last_year",
}


# ---------------------------------------------------------------------------
# Detection logic
# ---------------------------------------------------------------------------

def resolve_time(question: str) -> TimeResolution:
    """Detect time period and comparison intent from the question.

    Detection order (most specific first):
      1. "Same X" patterns (same_day_last_week, same_time_last_week, ...)
      2. Comparison prefix + base period (sammenlignet med i går → vs_yesterday)
      3. "Last N days" dynamic
      4. Base period alone (today, yesterday, ...)
    """
    result = TimeResolution()

    # Layer 1: "Same X" patterns
    for label, regex in _SAME_PATTERNS:
        m = regex.search(question)
        if m:
            result.comparison_period = label
            result.matched_text = m.group(0)
            # Also detect the base time period (usually today_sofar for time comparisons)
            for plabel, pregex in _BASE_PERIODS:
                pm = pregex.search(question)
                if pm:
                    result.time_period = plabel
                    break
            if not result.time_period:
                result.time_period = "today_sofar" if "time" in label else "today"
            return result

    # Layer 2: Comparison prefix + base period
    has_comparison = bool(_COMPARISON_PREFIX_RE.search(question))
    if has_comparison:
        for plabel, pregex in _BASE_PERIODS:
            pm = pregex.search(question)
            if pm:
                comp_label = _BASE_TO_COMPARISON.get(plabel)
                if comp_label:
                    result.comparison_period = comp_label
                    result.matched_text = pm.group(0)
                    # Also detect the primary time period
                    for plabel2, pregex2 in _BASE_PERIODS:
                        pm2 = pregex2.search(question)
                        if pm2 and plabel2 != plabel:
                            result.time_period = plabel2
                            break
                    if not result.time_period:
                        result.time_period = "today"
                    return result

    # Layer 3: "Last N days" dynamic
    m = _LAST_N_DAYS_RE.search(question)
    if m:
        result.time_period = "last_n_days"
        result.n_days = int(m.group(1))
        result.matched_text = m.group(0)
        return result

    # Layer 4: Base period alone
    for plabel, pregex in _BASE_PERIODS:
        pm = pregex.search(question)
        if pm:
            result.time_period = plabel
            result.matched_text = pm.group(0)
            return result

    return result


# ---------------------------------------------------------------------------
# Hint formatting
# ---------------------------------------------------------------------------

def format_time_hints(resolution: TimeResolution) -> str:
    """Format resolved time info into LLM-injectable hint block."""
    if not resolution.time_period and not resolution.comparison_period:
        return ""

    lines = ["TIME HINTS:"]

    # Comparison mode — two CTEs
    if resolution.comparison_period:
        comp = _COMPARISON_FILTERS.get(resolution.comparison_period)
        if comp:
            lines.append(f"Comparison detected: {resolution.comparison_period}")
            lines.append(f"  Note: {comp['note']}")
            lines.append("  Use two CTEs to compare periods:")
            lines.append(f"    current_period: {comp['current']}")
            lines.append(f"    previous_period: {comp['previous']}")
            lines.append("  Then JOIN or UNION the CTEs to show both side by side.")
            if "time" in resolution.comparison_period:
                lines.append("  ! order_time is TIME, CURRENT_TIME is TIMETZ. Cast: CURRENT_TIME::TIME")
            return "\n".join(lines)

    # Simple period
    if resolution.time_period == "last_n_days" and resolution.n_days:
        lines.append(f"Period: last {resolution.n_days} days")
        lines.append(f"  Filter: WHERE order_date >= CURRENT_DATE - INTERVAL '{resolution.n_days} days'")
    elif resolution.time_period:
        hint = _DATE_FILTERS.get(resolution.time_period)
        if hint:
            lines.append(f"Period: {resolution.time_period}")
            lines.append(f"  Filter: {hint}")

    # Intraday note
    if resolution.time_period in ("today", "today_sofar"):
        lines.append("  ! order_time is TIME, CURRENT_TIME is TIMETZ. Cast: CURRENT_TIME::TIME")

    return "\n".join(lines)


def format_trailing_hints(domains: set[str]) -> str:
    """When analytics domain is active, hint about trailing/benchmark tables."""
    if "analytics" not in domains:
        return ""

    return (
        "TRAILING METRICS (analytics tables):\n"
        "  t7/t28/t90 columns = rolling 7/28/90-day averages (no date filter needed)\n"
        "  wow_pct/mom_pct = week-over-week / month-over-month deltas\n"
        "  fleet_avg columns = chain-wide average for benchmarking\n"
        "  Use trailing tables for trend/benchmark questions — avoids scanning raw orders."
    )
