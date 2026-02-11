from pydantic import BaseModel
from typing import Optional

ALLOWED_MODELS = {
    "claude-opus-4-6",
    "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5-20251001",
    "ollama:sqlcoder",
    "ollama:duckdb-nsql",
}


class AskRequest(BaseModel):
    question: str
    model: str = "claude-sonnet-4-5-20250929"


class DashboardRequest(BaseModel):
    model: str = "claude-sonnet-4-5-20250929"


class ChartSpec(BaseModel):
    chart_type: str  # "bar", "line", "none"
    x_key: str = ""
    y_key: str = ""
    title: str = ""


class AskResponse(BaseModel):
    question: str
    sql: str
    columns: list[str]
    data: list[list]
    insight: str
    chart: ChartSpec
    model: str
    interaction_id: Optional[str] = None
    provider: Optional[str] = None
    sql_time_ms: Optional[int] = None
    insight_time_ms: Optional[int] = None
    query_time_ms: Optional[int] = None
    cached: bool = False
    cache_tier: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None


# Pricing per million tokens (USD)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # (input_per_M, output_per_M)
    "claude-opus-4-6": (15.0, 75.0),
    "claude-sonnet-4-5-20250929": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Estimate USD cost for a given model and token counts. Returns None for local models."""
    pricing = MODEL_PRICING.get(model)
    if not pricing:
        return None
    input_price, output_price = pricing
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000


class DashboardCard(BaseModel):
    title: str
    sql: str
    columns: list[str]
    data: list[list]
    insight: str
    chart: ChartSpec


class DashboardResponse(BaseModel):
    cards: list[DashboardCard]
    model: str
    cached: bool = False
