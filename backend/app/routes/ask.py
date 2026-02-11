import time
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from app.models import AskRequest, AskResponse, ChartSpec, ALLOWED_MODELS, estimate_cost
from app.llm_router import generate_sql, generate_insight, fix_sql
from app.database import execute_read_query
from app.tenant_context import inject_customer_filter
from app.auth.dependencies import get_optional_user
from app.auth.models import UserInfo
from app import logging_db, query_cache
from app.question_parser import parse_question

MAX_SQL_RETRIES = 1

router = APIRouter()


@router.post("/api/ask", response_model=AskResponse)
def ask(
    request_body: AskRequest,
    request: Request,
    user: UserInfo | None = Depends(get_optional_user),
):
    question = request_body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    model = request_body.model
    if model not in ALLOWED_MODELS:
        raise HTTPException(status_code=400, detail=f"Invalid model. Choose from: {sorted(ALLOWED_MODELS)}")

    # Check Ollama availability for ollama models
    if model.startswith("ollama:"):
        ollama_ok = getattr(request.app.state, "ollama_available", False)
        if not ollama_ok:
            raise HTTPException(
                status_code=503,
                detail="Ollama is not running. Start it with: ollama serve",
            )

    provider = "ollama" if model.startswith("ollama:") else "claude"

    # Extract customer_ids from authenticated user (empty = no filter / superadmin)
    customer_ids = user.customer_ids if user else []

    # --- Tier 0: Full Response Cache ---
    cached_resp = query_cache.get_cached_response(question, model)
    if cached_resp is not None:
        return AskResponse(**cached_resp, cached=True, cache_tier="response")

    # --- Tier 1: Common Questions Library ---
    common_sql = query_cache.match_common_question(question)
    if common_sql is not None:
        # Apply tenant filter to cached SQL
        if customer_ids:
            common_sql = inject_customer_filter(common_sql, customer_ids)
        return _execute_with_sql(
            question=question,
            sql=common_sql,
            model=model,
            provider=provider,
            sql_time_ms=0,
            cache_tier="common",
            customer_ids=customer_ids,
        )

    # --- Tier 2: SQL Cache ---
    cached_sql = query_cache.get_cached_sql(question, model)
    if cached_sql is not None:
        if customer_ids:
            cached_sql = inject_customer_filter(cached_sql, customer_ids)
        return _execute_with_sql(
            question=question,
            sql=cached_sql,
            model=model,
            provider=provider,
            sql_time_ms=0,
            cache_tier="sql",
            customer_ids=customer_ids,
        )

    # --- Tier 3: Full Pipeline ---
    t0 = time.perf_counter()
    try:
        sql, sql_usage = generate_sql(question, model, customer_ids=customer_ids or None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate SQL: {e}")
    sql_time_ms = int((time.perf_counter() - t0) * 1000)

    # Hard enforcement: inject customer_id filter if LLM missed it
    if customer_ids:
        sql = inject_customer_filter(sql, customer_ids)

    # Cache the generated SQL for future Tier 2 hits
    query_cache.put_cached_sql(question, model, sql)

    return _execute_with_sql(
        question=question,
        sql=sql,
        model=model,
        provider=provider,
        sql_time_ms=sql_time_ms,
        cache_tier=None,
        customer_ids=customer_ids,
        token_usage=sql_usage,
    )


def _execute_with_sql(
    *,
    question: str,
    sql: str,
    model: str,
    provider: str,
    sql_time_ms: int,
    cache_tier: str | None,
    customer_ids: list[int] | None = None,
    token_usage: dict | None = None,
) -> AskResponse:
    """Run query + insight generation, with auto-retry on SQL errors."""
    interaction_id = str(uuid.uuid4())
    total_input = (token_usage or {}).get("input_tokens", 0)
    total_output = (token_usage or {}).get("output_tokens", 0)

    t1 = time.perf_counter()
    try:
        columns, data = execute_read_query(sql)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid query: {e}")
    except Exception as e:
        # --- SQL retry: feed the error back to the LLM for correction ---
        original_error = str(e)
        original_sql = sql
        for attempt in range(MAX_SQL_RETRIES):
            try:
                t_fix = time.perf_counter()
                sql, fix_usage = fix_sql(question, sql, original_error, model)
                total_input += fix_usage.get("input_tokens", 0)
                total_output += fix_usage.get("output_tokens", 0)
                # Re-apply tenant filter on fixed SQL
                if customer_ids:
                    sql = inject_customer_filter(sql, customer_ids)
                fix_time_ms = int((time.perf_counter() - t_fix) * 1000)
                sql_time_ms += fix_time_ms
                columns, data = execute_read_query(sql)
                # Log the successful correction for learning
                print(f"[SQL-FIX] Retry {attempt+1} succeeded."
                      f"\n  Original: {original_sql}"
                      f"\n  Error:    {original_error}"
                      f"\n  Fixed:    {sql}")
                logging_db.log_sql_fix(
                    question=question,
                    model=model,
                    original_sql=original_sql,
                    error=original_error,
                    fixed_sql=sql,
                )
                break
            except ValueError as ve:
                raise HTTPException(status_code=400, detail=f"Invalid query: {ve}")
            except Exception:
                pass  # retry exhausted, fall through
        else:
            raise HTTPException(status_code=500, detail=f"Query execution failed: {original_error}")
    query_time_ms = int((time.perf_counter() - t1) * 1000)

    t2 = time.perf_counter()
    try:
        insight_data, insight_usage = generate_insight(question, sql, columns, data, model)
        total_input += insight_usage.get("input_tokens", 0)
        total_output += insight_usage.get("output_tokens", 0)
    except Exception as e:
        insight_data = {
            "insight": f"Query returned {len(data)} rows but insight generation failed: {e}",
            "chart_type": "none",
            "x_key": "",
            "y_key": "",
            "title": "",
        }
    insight_time_ms = int((time.perf_counter() - t2) * 1000)

    chart = ChartSpec(
        chart_type=insight_data.get("chart_type") or "none",
        x_key=insight_data.get("x_key") or "",
        y_key=insight_data.get("y_key") or "",
        title=insight_data.get("title") or "",
    )

    cost = estimate_cost(model, total_input, total_output) if (total_input + total_output) > 0 else None

    response = AskResponse(
        question=question,
        sql=sql,
        columns=columns,
        data=data,
        insight=insight_data.get("insight", ""),
        chart=chart,
        model=model,
        interaction_id=interaction_id,
        provider=provider,
        sql_time_ms=sql_time_ms,
        insight_time_ms=insight_time_ms,
        query_time_ms=query_time_ms,
        cached=cache_tier is not None,
        cache_tier=cache_tier,
        input_tokens=total_input if (total_input + total_output) > 0 else None,
        output_tokens=total_output if (total_input + total_output) > 0 else None,
        estimated_cost_usd=cost,
    )

    # Cache full response for future Tier 0 hits
    query_cache.put_cached_response(question, model, {
        "question": question,
        "sql": sql,
        "columns": columns,
        "data": data,
        "insight": insight_data.get("insight", ""),
        "chart": chart.model_dump(),
        "model": model,
        "interaction_id": interaction_id,
        "provider": provider,
        "sql_time_ms": sql_time_ms,
        "insight_time_ms": insight_time_ms,
        "query_time_ms": query_time_ms,
    })

    parsed = parse_question(question)

    logging_db.log_interaction(
        interaction_id=interaction_id,
        question=question,
        model=model,
        provider=provider,
        generated_sql=sql,
        query_succeeded=True,
        columns=columns,
        row_count=len(data),
        insight=insight_data.get("insight", ""),
        chart_type=chart.chart_type,
        sql_time_ms=sql_time_ms,
        insight_time_ms=insight_time_ms,
        query_time_ms=query_time_ms,
        matched_products=parsed["matched_products"],
        time_period=parsed["time_period"],
    )

    return response
