from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.models import ALLOWED_MODELS
from app.config import settings
from app.database import connect, close
from app.schema import discover_schema, get_table_count, build_product_catalog, precrunch_metadata
from app.ollama_client import check_ollama_available, close_http_client
from app import logging_db, management_db
from app.routes import ask, dashboard, schema_route, feedback, interactions, auth_routes, admin_routes, onboarding_routes
from app import query_cache


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Connecting to MotherDuck...")
    connect()
    discover_schema()
    print(f"Connected to MotherDuck. Discovered {get_table_count()} tables.")

    precrunch_metadata()
    build_product_catalog()

    # Generate SQL for common questions library against live schema
    print("Initializing common questions library...")
    query_cache.init_common_questions()

    # Connect logging DB (non-critical)
    logging_db.connect()

    # Connect management DB and create auth/tenant tables
    management_db.connect()

    # Seed superadmin if configured
    if settings.munuiq_admin_email and settings.munuiq_admin_password:
        from app.auth.passwords import hash_password
        management_db.seed_superadmin(
            email=settings.munuiq_admin_email,
            password_hash=hash_password(settings.munuiq_admin_password),
        )

    # Probe Ollama
    ollama_ok, ollama_models = check_ollama_available()
    app.state.ollama_available = ollama_ok
    app.state.ollama_models = ollama_models
    if ollama_ok:
        print(f"Ollama available. Models: {ollama_models}")
    else:
        print("Ollama not available. Ollama models will be disabled.")

    yield

    close_http_client()
    logging_db.close()
    management_db.close()
    close()
    print("Disconnected from MotherDuck.")


app = FastAPI(title="MUNUIQ - Restaurant AI Analytics", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ask.router)
app.include_router(dashboard.router)
app.include_router(schema_route.router)
app.include_router(feedback.router)
app.include_router(interactions.router)
app.include_router(auth_routes.router)
app.include_router(admin_routes.router)
app.include_router(onboarding_routes.router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "tables": get_table_count(),
        "models": sorted(ALLOWED_MODELS),
        "ollama_available": getattr(app.state, "ollama_available", False),
        "ollama_models": getattr(app.state, "ollama_models", []),
        "cache": query_cache.cache_stats(),
    }
