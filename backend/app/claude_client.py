import json
import anthropic
from app.config import settings
from app.schema import get_schema_context
from app.question_parser import build_query_hints

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key,
            max_retries=2,
        )
    return _client


def _parse_json(text: str) -> dict:
    """Parse JSON from LLM output, handling markdown fences."""
    import re
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try extracting from code fence
    m = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Try finding outermost braces
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return {
        "insight": text[:500],
        "chart_type": "none",
        "x_key": "",
        "y_key": "",
        "title": "",
    }


def _clean_sql(text: str) -> str:
    """Strip markdown fences and surrounding prose from LLM SQL output."""
    import re
    # Extract from ```sql ... ``` or ``` ... ```
    m = re.search(r"```(?:sql)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1)
    return text.strip().rstrip(";").strip()


def _usage(response) -> dict:
    """Extract token usage from an Anthropic response."""
    u = response.usage
    return {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens}


def generate_sql(question: str, model: str, customer_ids: list[int] | None = None) -> tuple[str, dict]:
    """Generate a SQL query from a natural language question. Returns (sql, usage)."""
    client = get_client()
    schema_ctx = get_schema_context()
    hints = build_query_hints(question)

    # Build customer_id constraint for tenant-scoped queries
    customer_constraint = ""
    if customer_ids:
        from app.tenant_context import build_customer_constraint
        customer_constraint = build_customer_constraint(customer_ids)

    response = client.messages.create(
        model=model,
        max_tokens=512,
        temperature=0,
        system=f"""SQL expert for DuckDB. Generate one SELECT query answering the question.

{schema_ctx}

Rules: ONLY the SQL, no explanation, no fences. SELECT only. LIMIT {settings.row_limit}. DuckDB syntax.
When matching product/article names, use short root stems with ILIKE to catch all spelling variants.
Always use table aliases and qualify every column with its alias to avoid ambiguous references.{customer_constraint}""",
        messages=[{"role": "user", "content": question + hints}],
    )
    return _clean_sql(response.content[0].text), _usage(response)


def fix_sql(question: str, sql: str, error: str, model: str) -> tuple[str, dict]:
    """Fix a failed SQL query given the DuckDB error message. Returns (sql, usage)."""
    client = get_client()
    schema_ctx = get_schema_context()

    response = client.messages.create(
        model=model,
        max_tokens=512,
        temperature=0,
        system=f"""SQL expert for DuckDB. Fix the SQL query that failed.

{schema_ctx}

Rules: ONLY the corrected SQL, no explanation, no fences. SELECT only. LIMIT {settings.row_limit}. DuckDB syntax.
Always use table aliases and qualify every column with its alias.""",
        messages=[
            {"role": "user", "content": f"Question: {question}\n\nFailed SQL:\n{sql}\n\nError: {error}\n\nFix the SQL:"},
        ],
    )
    return _clean_sql(response.content[0].text), _usage(response)


def generate_insight(question: str, sql: str, columns: list[str], data: list[list], model: str) -> tuple[dict, dict]:
    """Generate a narrative insight and chart spec from query results. Returns (insight_dict, usage)."""
    client = get_client()

    data_preview = data[:15]
    data_text = json.dumps({"columns": columns, "rows": data_preview}, default=str, separators=(",", ":"))
    if len(data) > 15:
        data_text += f"\n...({len(data)} rows total)"

    response = client.messages.create(
        model=model,
        max_tokens=512,
        temperature=0.3,
        system="""Analyze SQL results for restaurant dashboard. Return JSON only:
{"insight":"1-2 sentences","chart_type":"bar|line|none","x_key":"col","y_key":"col","title":"short"}
No fences. x_key/y_key must be actual column names. bar=categorical, line=time series, none=not chartable.""",
        messages=[
            {
                "role": "user",
                "content": f"Q: {question}\nSQL: {sql}\n{data_text}",
            }
        ],
    )

    text = response.content[0].text.strip()
    parsed = _parse_json(text)
    return parsed, _usage(response)


def generate_dashboard_queries(model: str) -> list[dict]:
    """Generate 4 interesting dashboard queries based on the schema."""
    client = get_client()
    schema_ctx = get_schema_context()

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        temperature=0.3,
        system=f"""Restaurant analytics expert. Given schema, generate 4 dashboard cards.

{schema_ctx}

Return JSON array of 4 objects: [{{"title":"...","sql":"SELECT ... LIMIT 50"}}]
No fences. Diverse insights (revenue, top items, busiest periods, categories). SELECT only.""",
        messages=[
            {
                "role": "user",
                "content": "Generate 4 diverse dashboard queries.",
            }
        ],
    )

    text = response.content[0].text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return []
