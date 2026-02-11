from fastapi import APIRouter, Depends, HTTPException, Request
from app.models import DashboardRequest, DashboardResponse, DashboardCard, ChartSpec, ALLOWED_MODELS
from app.llm_router import generate_dashboard_queries, generate_insight
from app.database import execute_read_query
from app.tenant_context import inject_customer_filter
from app.auth.dependencies import get_optional_user
from app.auth.models import UserInfo
from app import cache

router = APIRouter()

DASHBOARD_CACHE_TTL = 600  # 10 minutes


@router.post("/api/dashboard", response_model=DashboardResponse)
def get_dashboard(
    request_body: DashboardRequest,
    request: Request,
    user: UserInfo | None = Depends(get_optional_user),
):
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

    customer_ids = user.customer_ids if user else []

    cache_key = f"dashboard:{model}"
    cached = cache.get(cache_key)
    if cached is not None:
        return DashboardResponse(cards=cached, model=model, cached=True)

    try:
        queries = generate_dashboard_queries(model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate dashboard: {e}")

    if not queries:
        raise HTTPException(status_code=500, detail="No dashboard queries generated.")

    cards: list[DashboardCard] = []
    for q in queries[:4]:
        title = q.get("title", "Untitled")
        sql = q.get("sql", "")
        if not sql:
            continue

        # Apply tenant filter
        if customer_ids:
            sql = inject_customer_filter(sql, customer_ids)

        try:
            columns, data = execute_read_query(sql)
        except Exception:
            continue

        try:
            insight_data, _ = generate_insight(title, sql, columns, data, model)
        except Exception:
            insight_data = {
                "insight": f"Data for: {title}",
                "chart_type": "bar",
                "x_key": columns[0] if columns else "",
                "y_key": columns[1] if len(columns) > 1 else "",
                "title": title,
            }

        chart = ChartSpec(
            chart_type=insight_data.get("chart_type", "none"),
            x_key=insight_data.get("x_key", ""),
            y_key=insight_data.get("y_key", ""),
            title=insight_data.get("title", title),
        )

        cards.append(
            DashboardCard(
                title=title,
                sql=sql,
                columns=columns,
                data=data,
                insight=insight_data.get("insight", ""),
                chart=chart,
            )
        )

    cache.put(cache_key, cards, DASHBOARD_CACHE_TTL)
    return DashboardResponse(cards=cards, model=model, cached=False)
