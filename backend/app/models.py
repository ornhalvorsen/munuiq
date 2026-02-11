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
    provider: Optional[str] = None
    sql_time_ms: Optional[int] = None
    insight_time_ms: Optional[int] = None
    query_time_ms: Optional[int] = None


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
