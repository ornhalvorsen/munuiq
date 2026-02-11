"""Thin dispatcher that routes LLM calls to Claude or Ollama based on model prefix."""

from app import claude_client, ollama_client


def _is_ollama(model: str) -> bool:
    return model.startswith("ollama:")


def generate_sql(question: str, model: str) -> str:
    if _is_ollama(model):
        return ollama_client.generate_sql(question, model)
    return claude_client.generate_sql(question, model)


def generate_insight(
    question: str, sql: str, columns: list[str], data: list[list], model: str
) -> dict:
    if _is_ollama(model):
        return ollama_client.generate_insight(question, sql, columns, data, model)
    return claude_client.generate_insight(question, sql, columns, data, model)


def generate_dashboard_queries(model: str) -> list[dict]:
    if _is_ollama(model):
        return ollama_client.generate_dashboard_queries(model)
    return claude_client.generate_dashboard_queries(model)
