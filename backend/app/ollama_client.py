import json
import re
import httpx
from app.config import settings
from app.schema import get_schema_context

_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            base_url=settings.ollama_base_url,
            timeout=settings.ollama_timeout,
        )
    return _client


def close_http_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def check_ollama_available() -> tuple[bool, list[str]]:
    """Probe Ollama /api/tags to check availability and list loaded models."""
    try:
        client = _get_client()
        resp = client.get("/api/tags")
        resp.raise_for_status()
        data = resp.json()
        model_names = [m["name"] for m in data.get("models", [])]
        return True, model_names
    except Exception:
        return False, []


def _extract_sql(text: str) -> str:
    """Robustly extract SQL from model output that may include fences or explanation."""
    # Try code fence first
    fence_match = re.search(r"```(?:sql)?\s*\n?(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()

    # Try to find SELECT/WITH statement
    sql_match = re.search(r"((?:WITH|SELECT)\b.*)", text, re.DOTALL | re.IGNORECASE)
    if sql_match:
        sql = sql_match.group(1).strip()
        # Remove trailing explanation after semicolon
        semi_idx = sql.find(";")
        if semi_idx != -1:
            sql = sql[: semi_idx + 1]
        return sql

    return text.strip()


def _fixup_duckdb_sql(sql: str) -> str:
    """Post-process common PostgreSQL-isms into DuckDB syntax."""
    # to_char(col, 'format') -> strftime(col, 'format')
    sql = re.sub(
        r"\bto_char\s*\(\s*(.+?)\s*,\s*'(.+?)'\s*\)",
        r"strftime('\2', \1)",
        sql,
        flags=re.IGNORECASE,
    )
    # EXTRACT(EPOCH FROM col) -> epoch(col)
    sql = re.sub(
        r"\bEXTRACT\s*\(\s*EPOCH\s+FROM\s+(.+?)\)",
        r"epoch(\1)",
        sql,
        flags=re.IGNORECASE,
    )
    # NOW() -> current_timestamp
    sql = re.sub(r"\bNOW\s*\(\s*\)", "current_timestamp", sql, flags=re.IGNORECASE)
    # ILIKE is supported in DuckDB, no change needed
    # STRING_AGG -> string_agg (case fix only, both work)
    # COALESCE, CASE, etc. are standard SQL — no changes needed
    return sql


def _parse_json_response(text: str) -> dict:
    """3-level fallback JSON parsing: direct -> fence extraction -> brace extraction -> fallback."""
    # Level 1: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Level 2: extract from code fence
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Level 3: find outermost braces
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end > brace_start:
        try:
            return json.loads(text[brace_start : brace_end + 1])
        except json.JSONDecodeError:
            pass

    # Fallback
    return {
        "insight": text.strip()[:500],
        "chart_type": "none",
        "x_key": "",
        "y_key": "",
        "title": "",
    }


def _parse_json_array_response(text: str) -> list[dict]:
    """Parse a JSON array from model output with fallback extraction."""
    # Level 1: direct parse
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Level 2: extract from code fence
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence_match:
        try:
            result = json.loads(fence_match.group(1).strip())
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    # Level 3: find outermost brackets
    bracket_start = text.find("[")
    bracket_end = text.rfind("]")
    if bracket_start != -1 and bracket_end > bracket_start:
        try:
            result = json.loads(text[bracket_start : bracket_end + 1])
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    return []


def _build_sql_prompt(question: str, model: str) -> str:
    """Build model-specific SQL generation prompt."""
    schema_ctx = get_schema_context()
    ollama_model = model.removeprefix("ollama:")

    if ollama_model == "duckdb-nsql":
        # DuckDB-NSQL uses its native prompt format
        return f"""### Task
Generate a SQL query to answer: {question}

### Database
DuckDB

### Schema
{schema_ctx}

### SQL
"""
    else:
        # SQLCoder / generic: explicit DuckDB hints
        return f"""Generate a DuckDB SQL query to answer the following question.

{schema_ctx}

IMPORTANT DuckDB syntax rules:
- Use strftime(format, col) NOT to_char()
- Use epoch(col) NOT EXTRACT(EPOCH FROM ...)
- Use current_timestamp NOT NOW()
- Use DATE_TRUNC('period', col) for date truncation
- Use || for string concatenation
- LIMIT {settings.row_limit} max rows

Question: {question}

Return ONLY the SQL query, no explanation, no code fences. SELECT only."""


def generate_sql(question: str, model: str) -> str:
    """Generate SQL via Ollama. Model should be like 'ollama:sqlcoder'."""
    client = _get_client()
    ollama_model = model.removeprefix("ollama:")

    prompt = _build_sql_prompt(question, model)

    resp = client.post(
        "/api/generate",
        json={
            "model": ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0, "num_predict": 512},
        },
    )
    resp.raise_for_status()
    raw = resp.json().get("response", "")
    sql = _extract_sql(raw)
    sql = _fixup_duckdb_sql(sql)
    return sql


def generate_insight(
    question: str, sql: str, columns: list[str], data: list[list], model: str
) -> dict:
    """Generate insight using the Ollama insight model (Mistral). The SQL model parameter is ignored for insight generation."""
    client = _get_client()
    insight_model = settings.ollama_insight_model

    data_preview = data[:15]
    data_text = json.dumps(
        {"columns": columns, "rows": data_preview}, default=str, separators=(",", ":")
    )
    if len(data) > 15:
        data_text += f"\n...({len(data)} rows total)"

    prompt = f"""Analyze SQL results for restaurant dashboard. Return JSON only:
{{"insight":"1-2 sentences","chart_type":"bar|line|none","x_key":"col","y_key":"col","title":"short"}}
No fences. x_key/y_key must be actual column names. bar=categorical, line=time series, none=not chartable.

Q: {question}
SQL: {sql}
{data_text}"""

    resp = client.post(
        "/api/generate",
        json={
            "model": insight_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 512},
        },
    )
    resp.raise_for_status()
    raw = resp.json().get("response", "")
    return _parse_json_response(raw)


def generate_dashboard_queries(model: str) -> list[dict]:
    """Generate dashboard queries using Mistral (SQL models can't reliably produce JSON)."""
    client = _get_client()
    insight_model = settings.ollama_insight_model
    schema_ctx = get_schema_context()

    prompt = f"""Restaurant analytics expert. Given schema, generate 4 dashboard cards.

{schema_ctx}

Return JSON array of 4 objects: [{{"title":"...","sql":"SELECT ... LIMIT 50"}}]
No fences. Diverse insights (revenue, top items, busiest periods, categories). SELECT only. Use DuckDB syntax."""

    resp = client.post(
        "/api/generate",
        json={
            "model": insight_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 1024},
        },
    )
    resp.raise_for_status()
    raw = resp.json().get("response", "")
    return _parse_json_array_response(raw)
