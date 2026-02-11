"""Thin dispatcher that routes LLM calls to Claude or Ollama based on model prefix."""

from app import claude_client, ollama_client


def _is_ollama(model: str) -> bool:
    return model.startswith("ollama:")


def generate_sql(question: str, model: str, customer_ids: list[int] | None = None) -> tuple[str, dict]:
    if _is_ollama(model):
        return ollama_client.generate_sql(question, model, customer_ids=customer_ids)
    return claude_client.generate_sql(question, model, customer_ids=customer_ids)


def fix_sql(question: str, sql: str, error: str, model: str) -> tuple[str, dict]:
    if _is_ollama(model):
        return ollama_client.fix_sql(question, sql, error, model)
    return claude_client.fix_sql(question, sql, error, model)


def generate_insight(
    question: str, sql: str, columns: list[str], data: list[list], model: str
) -> tuple[dict, dict]:
    if _is_ollama(model):
        return ollama_client.generate_insight(question, sql, columns, data, model)
    return claude_client.generate_insight(question, sql, columns, data, model)


def generate_dashboard_queries(model: str) -> list[dict]:
    if _is_ollama(model):
        return ollama_client.generate_dashboard_queries(model)
    return claude_client.generate_dashboard_queries(model)
