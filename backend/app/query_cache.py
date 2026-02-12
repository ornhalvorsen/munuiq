"""
Tiered query cache for /api/ask.

Tier 0: Full response cache (30 min TTL) — skips everything
Tier 1: Common questions library — skips generate_sql LLM call
Tier 2: SQL cache (no expiry) — skips generate_sql LLM call
Tier 3: Full pipeline (no cache)
"""

import re
import time
import unicodedata

# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def normalize_question(q: str) -> str:
    """Lowercase, strip accents, remove punctuation, collapse whitespace."""
    q = q.lower().strip()
    # Strip accents
    q = "".join(
        c for c in unicodedata.normalize("NFD", q)
        if unicodedata.category(c) != "Mn"
    )
    # Remove punctuation (keep alphanumeric + spaces)
    q = re.sub(r"[^a-z0-9\s]", "", q)
    # Collapse whitespace
    q = re.sub(r"\s+", " ", q).strip()
    return q


# ---------------------------------------------------------------------------
# Tier 1: Common Questions Library
# ---------------------------------------------------------------------------
# SQL is auto-generated at startup via init_common_questions().
# Only patterns + description are static.

COMMON_QUESTIONS: list[dict] = [
    {
        "patterns": [
            r"(?:top|best)\s*sell(?:ing|er)?\s*(?:items?|products?|dishes?|menu)?",
            r"most\s*(?:popular|sold)\s*(?:items?|products?|dishes?|menu)?",
        ],
        "description": "Top 20 best selling items ranked by total quantity sold",
    },
    {
        "patterns": [
            r"(?:worst|least|bottom)\s*sell(?:ing|er)?\s*(?:items?|products?|dishes?|menu)?",
            r"least\s*(?:popular|sold)\s*(?:items?|products?|dishes?|menu)?",
        ],
        "description": "Bottom 20 least selling items ranked by total quantity sold ascending",
    },
    {
        "patterns": [
            r"(?:sales?|revenue)\s*(?:over\s*time|trend|by\s*(?:day|date))",
            r"daily\s*(?:sales?|revenue)",
        ],
        "description": "Daily revenue trend over time, limit 200 days",
    },
    {
        "patterns": [
            r"revenue\s*by\s*(?:day\s*of\s*week|weekday)",
            r"busiest\s*day(?:s)?",
            r"(?:which|what)\s*day.*(?:most|busiest|highest)",
        ],
        "description": "Total revenue and order count by day of week",
    },
    {
        "patterns": [
            r"revenue\s*by\s*(?:hour|time)",
            r"(?:peak|busiest)\s*hours?",
            r"(?:which|what)\s*(?:hour|time).*(?:most|busiest|peak)",
        ],
        "description": "Total revenue and order count by hour of day",
    },
    {
        "patterns": [
            r"revenue\s*by\s*categor(?:y|ies)",
            r"categor(?:y|ies)\s*(?:breakdown|split|revenue)",
        ],
        "description": "Revenue breakdown by product category",
    },
    {
        "patterns": [
            r"total\s*revenue",
            r"how\s*much\s*(?:revenue|sales|money)",
            r"(?:total|overall)\s*sales",
        ],
        "description": "Summary statistics: total orders, total revenue, average order value",
    },
    {
        "patterns": [
            r"average\s*order\s*value",
            r"\baov\b",
            r"avg\s*order",
        ],
        "description": "Average order value per day over time, limit 200 days",
    },
]

# Filled at startup by init_common_questions()
_common_sql: dict[int, str] = {}

# Pre-compile patterns (index-based lookup into _common_sql)
_compiled_patterns: list[tuple[list[re.Pattern], int]] = []
for _i, _entry in enumerate(COMMON_QUESTIONS):
    _compiled = [re.compile(p, re.IGNORECASE) for p in _entry["patterns"]]
    _compiled_patterns.append((_compiled, _i))

_init_model = "claude-haiku-4-5-20251001"


def init_common_questions() -> None:
    """Generate real SQL for each common question using the LLM + live schema.

    Called once at startup after discover_schema(). Uses Haiku for speed/cost.
    Failures are logged and skipped — that question just won't match Tier 1.
    """
    from app.llm_router import generate_sql

    count = 0
    for i, entry in enumerate(COMMON_QUESTIONS):
        try:
            sql = generate_sql(entry["description"], _init_model)
            _common_sql[i] = sql
            count += 1
        except Exception as e:
            print(f"[query_cache] Failed to init common question {i} ({entry['description']}): {e}")

    print(f"[query_cache] Initialized {count}/{len(COMMON_QUESTIONS)} common questions")


def match_common_question(question: str) -> str | None:
    """Match question against common patterns. Returns pre-generated SQL or None."""
    normalized = normalize_question(question)
    for patterns, idx in _compiled_patterns:
        if idx not in _common_sql:
            continue
        for pattern in patterns:
            if pattern.search(normalized):
                return _common_sql[idx]
    return None


# ---------------------------------------------------------------------------
# Tier 2: SQL Cache (no expiry)
# ---------------------------------------------------------------------------

_sql_store: dict[str, str] = {}


def _sql_key(question: str, model: str) -> str:
    return f"sql:{normalize_question(question)}:{model}"


def get_cached_sql(question: str, model: str) -> str | None:
    return _sql_store.get(_sql_key(question, model))


def put_cached_sql(question: str, model: str, sql: str) -> None:
    _sql_store[_sql_key(question, model)] = sql


# ---------------------------------------------------------------------------
# Tier 0: Full Response Cache (30 min TTL)
# ---------------------------------------------------------------------------

_response_store: dict[str, tuple[dict, float]] = {}
_RESPONSE_TTL = 1800  # 30 minutes

# Time-sensitive keywords — queries containing these should not be response-cached
# because the underlying data changes frequently (e.g. "sales today" at 8am vs 10am)
_TIME_SENSITIVE_RE = re.compile(
    r"\b(today|i\s*dag|yesterday|i\s*gar|this\s*week|denne\s*uken|"
    r"this\s*month|denne\s*maneden|right\s*now|akkurat\s*na|"
    r"last\s*hour|siste\s*time[n]?)\b",
    re.IGNORECASE,
)


def is_time_sensitive(question: str) -> bool:
    """Return True if the question references a time period that changes."""
    return bool(_TIME_SENSITIVE_RE.search(question))


def _response_key(question: str, model: str) -> str:
    return f"resp:{normalize_question(question)}:{model}"


def get_cached_response(question: str, model: str) -> dict | None:
    # Never serve cached responses for time-sensitive queries
    if is_time_sensitive(question):
        return None
    key = _response_key(question, model)
    entry = _response_store.get(key)
    if entry is None:
        return None
    data, ts = entry
    if time.time() - ts > _RESPONSE_TTL:
        del _response_store[key]
        return None
    return data


def put_cached_response(question: str, model: str, response_dict: dict) -> None:
    # Don't cache time-sensitive responses — they go stale too quickly
    if is_time_sensitive(question):
        return
    key = _response_key(question, model)
    _response_store[key] = (response_dict, time.time())


# ---------------------------------------------------------------------------
# Cache invalidation
# ---------------------------------------------------------------------------

def clear_all() -> None:
    """Invalidate all caches. Called after onboarding approval changes category mappings."""
    _response_store.clear()
    _sql_store.clear()
    _common_sql.clear()
    init_common_questions()  # regenerate with current schema context


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def cache_stats() -> dict:
    """Return cache sizes for monitoring."""
    # Count non-expired response entries
    now = time.time()
    active_responses = sum(
        1 for _, (__, ts) in _response_store.items()
        if now - ts <= _RESPONSE_TTL
    )
    return {
        "response_cache_entries": active_responses,
        "sql_cache_entries": len(_sql_store),
        "common_questions_count": len(COMMON_QUESTIONS),
        "common_questions_ready": len(_common_sql),
    }
