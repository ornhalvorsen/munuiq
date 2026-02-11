import time
from fastapi import APIRouter, HTTPException, Request
from app.models import AskRequest, AskResponse, ChartSpec, ALLOWED_MODELS
from app.llm_router import generate_sql, generate_insight
from app.database import execute_read_query

router = APIRouter()


@router.post("/api/ask", response_model=AskResponse)
def ask(request_body: AskRequest, request: Request):
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

    t0 = time.perf_counter()
    try:
        sql = generate_sql(question, model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate SQL: {e}")
    sql_time_ms = int((time.perf_counter() - t0) * 1000)

    t1 = time.perf_counter()
    try:
        columns, data = execute_read_query(sql)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid query: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query execution failed: {e}")
    query_time_ms = int((time.perf_counter() - t1) * 1000)

    t2 = time.perf_counter()
    try:
        insight_data = generate_insight(question, sql, columns, data, model)
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
        chart_type=insight_data.get("chart_type", "none"),
        x_key=insight_data.get("x_key", ""),
        y_key=insight_data.get("y_key", ""),
        title=insight_data.get("title", ""),
    )

    return AskResponse(
        question=question,
        sql=sql,
        columns=columns,
        data=data,
        insight=insight_data.get("insight", ""),
        chart=chart,
        model=model,
        provider=provider,
        sql_time_ms=sql_time_ms,
        insight_time_ms=insight_time_ms,
        query_time_ms=query_time_ms,
    )
