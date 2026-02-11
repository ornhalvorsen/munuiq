from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.models import ALLOWED_MODELS
from app.database import connect, close
from app.schema import discover_schema, get_table_count
from app.ollama_client import check_ollama_available, close_http_client
from app.routes import ask, dashboard, schema_route


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Connecting to MotherDuck...")
    connect()
    discover_schema()
    print(f"Connected to MotherDuck. Discovered {get_table_count()} tables.")

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
    close()
    print("Disconnected from MotherDuck.")


app = FastAPI(title="MUNUIQ - Restaurant AI Analytics", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ask.router)
app.include_router(dashboard.router)
app.include_router(schema_route.router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "tables": get_table_count(),
        "models": sorted(ALLOWED_MODELS),
        "ollama_available": getattr(app.state, "ollama_available", False),
        "ollama_models": getattr(app.state, "ollama_models", []),
    }
