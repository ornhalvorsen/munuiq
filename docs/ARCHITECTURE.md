# AnalyticsIQ Architecture Guide

> Restaurant AI Analytics Platform — FastAPI + React + DDD

---

## Table of Contents

1. [Principles](#principles)
2. [Domain-Driven Design Layers](#domain-driven-design-layers)
3. [Project Structure](#project-structure)
4. [Domain Boundaries](#domain-boundaries)
5. [Layer Rules & Dependencies](#layer-rules--dependencies)
6. [FastAPI Patterns](#fastapi-patterns)
7. [Configuration](#configuration)
8. [Testing Strategy](#testing-strategy)
9. [Conventions](#conventions)

---

## Principles

1. **Domain-first** — Business logic lives in the domain layer, free of framework dependencies.
2. **Dependency inversion** — Inner layers define interfaces; outer layers implement them.
3. **Explicit boundaries** — Each bounded context owns its models, services, and repository contracts.
4. **Security by default** — Auth, input validation, and sanitization are infrastructure concerns, enforced at the boundary.
5. **Fail fast, fail loud** — Domain exceptions propagate to a centralized error handler. No silent swallowing.

---

## Domain-Driven Design Layers

```
┌─────────────────────────────────────────────────────────┐
│                   INTERFACES (API)                      │
│  FastAPI routers, middleware, request/response schemas   │
├─────────────────────────────────────────────────────────┤
│                   APPLICATION                           │
│  Use cases, orchestration, DTOs, command/query handlers │
├─────────────────────────────────────────────────────────┤
│                   DOMAIN                                │
│  Entities, value objects, domain services, repo ABCs    │
├─────────────────────────────────────────────────────────┤
│                   INFRASTRUCTURE                        │
│  DB repos, external clients, auth, caching, migrations  │
└─────────────────────────────────────────────────────────┘
```

**Dependency direction: top → bottom, but Domain NEVER imports from layers above it.**

---

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                         # FastAPI app factory & lifespan
│   ├── config.py                       # pydantic-settings configuration
│   ├── dependencies.py                 # Top-level FastAPI DI providers
│   │
│   ├── domain/                         # === DOMAIN LAYER ===
│   │   ├── __init__.py
│   │   ├── analytics/                  # Bounded Context: AI Analytics
│   │   │   ├── __init__.py
│   │   │   ├── entities.py             # Query, Insight, ChartSpec
│   │   │   ├── value_objects.py        # SQLStatement, NaturalLanguageQuestion
│   │   │   ├── services.py            # Query validation, insight rules
│   │   │   ├── repositories.py         # ABC: AnalyticsRepository
│   │   │   └── exceptions.py          # QueryGenerationError, UnsafeQueryError
│   │   │
│   │   ├── restaurant/                 # Bounded Context: Restaurant Data
│   │   │   ├── __init__.py
│   │   │   ├── entities.py             # Schema, Table, Column
│   │   │   ├── value_objects.py        # TableName, ColumnType
│   │   │   ├── repositories.py         # ABC: SchemaRepository
│   │   │   └── exceptions.py
│   │   │
│   │   ├── dashboard/                  # Bounded Context: Dashboard
│   │   │   ├── __init__.py
│   │   │   ├── entities.py             # DashboardCard, DashboardLayout
│   │   │   ├── services.py            # Card generation rules
│   │   │   ├── repositories.py         # ABC: DashboardRepository
│   │   │   └── exceptions.py
│   │   │
│   │   └── shared/                     # Shared Kernel
│   │       ├── __init__.py
│   │       ├── value_objects.py        # Pagination, DateRange
│   │       └── exceptions.py          # DomainError base class
│   │
│   ├── application/                    # === APPLICATION LAYER ===
│   │   ├── __init__.py
│   │   ├── analytics/
│   │   │   ├── __init__.py
│   │   │   ├── ask_question.py         # Use case: process natural language query
│   │   │   └── dtos.py                # AskQuestionCommand, QueryResultDTO
│   │   │
│   │   ├── restaurant/
│   │   │   ├── __init__.py
│   │   │   ├── get_schema.py           # Use case: retrieve schema
│   │   │   └── dtos.py
│   │   │
│   │   └── dashboard/
│   │       ├── __init__.py
│   │       ├── generate_dashboard.py   # Use case: build dashboard
│   │       └── dtos.py
│   │
│   ├── infrastructure/                 # === INFRASTRUCTURE LAYER ===
│   │   ├── __init__.py
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   ├── connection.py           # DuckDB/MotherDuck connection pool
│   │   │   ├── repositories/           # Concrete repo implementations
│   │   │   │   ├── __init__.py
│   │   │   │   ├── analytics_repo.py
│   │   │   │   ├── schema_repo.py
│   │   │   │   └── dashboard_repo.py
│   │   │   └── migrations/
│   │   │       └── ...
│   │   │
│   │   ├── external/
│   │   │   ├── __init__.py
│   │   │   └── claude_client.py        # Anthropic API wrapper
│   │   │
│   │   └── security/
│   │       ├── __init__.py
│   │       ├── auth.py                 # JWT validation, token handling
│   │       ├── rate_limiter.py         # Request rate limiting
│   │       └── sanitization.py         # SQL/input sanitization
│   │
│   └── interfaces/                     # === INTERFACE LAYER ===
│       ├── __init__.py
│       ├── api/
│       │   ├── __init__.py
│       │   ├── v1/
│       │   │   ├── __init__.py
│       │   │   ├── router.py           # Aggregate v1 router
│       │   │   ├── analytics.py        # POST /api/v1/ask
│       │   │   ├── dashboard.py        # GET  /api/v1/dashboard
│       │   │   └── schema.py           # GET  /api/v1/schema
│       │   └── deps.py                # Route-scoped dependencies
│       │
│       └── middleware/
│           ├── __init__.py
│           ├── error_handler.py        # Global exception → HTTP response
│           ├── request_logging.py      # Structured request/response logging
│           ├── cors.py                 # CORS configuration
│           └── security_headers.py     # HSTS, CSP, X-Frame-Options
│
├── tests/
│   ├── conftest.py                     # Shared fixtures
│   ├── unit/
│   │   ├── domain/                     # Pure logic tests (no IO)
│   │   └── application/               # Use case tests (mocked repos)
│   ├── integration/
│   │   └── infrastructure/            # DB, external client tests
│   └── e2e/
│       └── api/                        # Full HTTP round-trip tests
│
├── .env.example
├── pyproject.toml
└── requirements.txt

frontend/
├── src/
│   ├── api/
│   │   └── client.ts                   # Typed API client
│   ├── components/
│   │   ├── chat/                       # Chat feature components
│   │   ├── dashboard/                  # Dashboard feature components
│   │   └── shared/                     # Shared UI components
│   ├── hooks/                          # Custom React hooks
│   ├── types/
│   │   └── index.ts                    # TypeScript interfaces
│   ├── context/                        # React context providers
│   ├── App.tsx
│   └── main.tsx
├── package.json
├── vite.config.ts
└── tsconfig.json
```

---

## Domain Boundaries

### Analytics (Core Domain)

The heart of the system. Owns the workflow of:
- Receiving a natural language question
- Generating safe SQL via Claude
- Executing the query
- Producing an insight + chart specification

**Key entities:** `Query`, `Insight`, `ChartSpec`
**Key value objects:** `SQLStatement` (validated, read-only SQL), `NaturalLanguageQuestion`
**Domain service:** `QueryValidator` — enforces SQL safety rules (SELECT/WITH only, no DDL/DML)

### Restaurant (Supporting Domain)

Owns the database schema model. The analytics domain depends on schema information but does not own it.

**Key entities:** `DatabaseSchema`, `Table`, `Column`
**Repository contract:** `SchemaRepository` — discover and cache schema from MotherDuck

### Dashboard (Supporting Domain)

Owns pre-generated insight cards and layout logic.

**Key entities:** `DashboardCard`, `DashboardLayout`
**Domain service:** `CardGenerator` — rules for diverse, non-overlapping cards

### Shared Kernel

Cross-cutting value objects and base exceptions used by all bounded contexts.

---

## Layer Rules & Dependencies

| Layer          | Can Import From            | Cannot Import From       |
|----------------|----------------------------|--------------------------|
| Domain         | Python stdlib, shared kernel | Application, Infrastructure, Interfaces |
| Application    | Domain                     | Infrastructure, Interfaces |
| Infrastructure | Domain, Application        | Interfaces               |
| Interfaces     | Application, Infrastructure (via DI) | Domain (directly) |

### Enforcing the Rules

- **Domain layer has zero framework imports.** No FastAPI, no DuckDB, no httpx. Pure Python + dataclasses/Pydantic models.
- **Application layer orchestrates.** It calls domain services and repository interfaces. It receives concrete implementations via dependency injection.
- **Infrastructure implements.** Repository ABCs from the domain layer are implemented here with real DB calls, API clients, etc.
- **Interfaces translate.** HTTP requests → application DTOs. Application responses → HTTP responses.

### Dependency Injection with FastAPI

FastAPI's `Depends()` is the DI mechanism. Wire it in `app/dependencies.py`:

```python
# app/dependencies.py
from functools import lru_cache
from app.config import Settings
from app.infrastructure.database.connection import get_db_connection
from app.infrastructure.database.repositories.analytics_repo import DuckDBAnalyticsRepository
from app.infrastructure.external.claude_client import ClaudeClient
from app.domain.analytics.repositories import AnalyticsRepository

@lru_cache
def get_settings() -> Settings:
    return Settings()

def get_analytics_repository(
    settings: Settings = Depends(get_settings),
) -> AnalyticsRepository:
    conn = get_db_connection(settings)
    return DuckDBAnalyticsRepository(conn)

def get_claude_client(
    settings: Settings = Depends(get_settings),
) -> ClaudeClient:
    return ClaudeClient(api_key=settings.anthropic_api_key, model=settings.claude_model)
```

---

## FastAPI Patterns

### App Factory (`main.py`)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.interfaces.api.v1.router import v1_router
from app.interfaces.middleware.error_handler import register_error_handlers
from app.interfaces.middleware.cors import configure_cors
from app.interfaces.middleware.security_headers import SecurityHeadersMiddleware
from app.interfaces.middleware.request_logging import RequestLoggingMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: warm caches, discover schema, validate connections
    yield
    # Shutdown: close connections

def create_app() -> FastAPI:
    app = FastAPI(
        title="AnalyticsIQ API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # Middleware (order matters — outermost first)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    configure_cors(app)

    # Error handlers
    register_error_handlers(app)

    # Routers
    app.include_router(v1_router, prefix="/api/v1")

    return app

app = create_app()
```

### Router Pattern

Each router file maps to one bounded context. Keep routes thin — delegate to application layer immediately.

```python
# app/interfaces/api/v1/analytics.py
from fastapi import APIRouter, Depends
from app.application.analytics.ask_question import AskQuestionHandler
from app.application.analytics.dtos import AskQuestionCommand, QueryResultDTO
from app.interfaces.api.deps import get_ask_question_handler

router = APIRouter(prefix="/ask", tags=["analytics"])

@router.post("", response_model=QueryResultDTO)
async def ask_question(
    command: AskQuestionCommand,
    handler: AskQuestionHandler = Depends(get_ask_question_handler),
) -> QueryResultDTO:
    return await handler.execute(command)
```

### Use Case Pattern

Each use case is a single class with an `execute` method. It orchestrates domain services and repositories.

```python
# app/application/analytics/ask_question.py
from app.domain.analytics.services import QueryValidator
from app.domain.analytics.repositories import AnalyticsRepository
from app.infrastructure.external.claude_client import ClaudeClient
from .dtos import AskQuestionCommand, QueryResultDTO

class AskQuestionHandler:
    def __init__(
        self,
        repo: AnalyticsRepository,
        claude: ClaudeClient,
        validator: QueryValidator,
    ):
        self._repo = repo
        self._claude = claude
        self._validator = validator

    async def execute(self, command: AskQuestionCommand) -> QueryResultDTO:
        schema = await self._repo.get_schema()
        sql = await self._claude.generate_sql(command.question, schema)
        self._validator.validate(sql)  # raises UnsafeQueryError if bad
        result = await self._repo.execute_query(sql)
        insight = await self._claude.generate_insight(command.question, result)
        return QueryResultDTO(
            question=command.question,
            sql=str(sql),
            columns=result.columns,
            data=result.rows,
            insight=insight.text,
            chart=insight.chart_spec,
        )
```

### Error Handling

Map domain exceptions to HTTP responses in one place:

```python
# app/interfaces/middleware/error_handler.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.domain.shared.exceptions import DomainError
from app.domain.analytics.exceptions import UnsafeQueryError, QueryGenerationError

def register_error_handlers(app: FastAPI):
    @app.exception_handler(UnsafeQueryError)
    async def unsafe_query_handler(request: Request, exc: UnsafeQueryError):
        return JSONResponse(status_code=400, content={"error": str(exc), "code": "UNSAFE_QUERY"})

    @app.exception_handler(QueryGenerationError)
    async def query_gen_handler(request: Request, exc: QueryGenerationError):
        return JSONResponse(status_code=422, content={"error": str(exc), "code": "QUERY_GENERATION_FAILED"})

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError):
        return JSONResponse(status_code=400, content={"error": str(exc), "code": "DOMAIN_ERROR"})

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        # Log the full traceback, return generic message
        return JSONResponse(status_code=500, content={"error": "Internal server error"})
```

### Standardized API Responses

All endpoints return a consistent envelope when needed:

```python
# For list/collection endpoints, use this pattern:
{
    "data": [...],
    "meta": {"total": 42, "page": 1, "per_page": 20}
}

# For single-resource endpoints:
{
    "data": {...}
}

# For errors:
{
    "error": "Human-readable message",
    "code": "MACHINE_READABLE_CODE"
}
```

---

## Configuration

Use `pydantic-settings` for type-safe, validated configuration:

```python
# app/config.py
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # API
    app_env: str = Field(default="development", description="development | staging | production")
    debug: bool = Field(default=False)
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    allowed_origins: list[str] = Field(default=["http://localhost:5173"])

    # Database
    motherduck_token: str
    motherduck_database: str = Field(default="Kanelsnurren")

    # AI
    anthropic_api_key: str
    claude_model: str = Field(default="claude-sonnet-4-5-20250929")
    row_limit: int = Field(default=500)

    # Security
    jwt_secret: str = Field(default="")
    jwt_algorithm: str = Field(default="HS256")
    rate_limit_per_minute: int = Field(default=60)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
```

---

## Testing Strategy

### Test Pyramid

```
         ╱ E2E ╲           Few — full HTTP, real DB (CI only)
        ╱────────╲
       ╱Integration╲       Some — real DB, real clients
      ╱──────────────╲
     ╱   Unit Tests    ╲    Many — fast, no IO, mocked deps
    ╱────────────────────╲
```

### Unit Tests (Domain + Application)

- Test domain services and value objects with plain assertions.
- Test use case handlers with mocked repository and client dependencies.
- **Zero IO.** These run in milliseconds.

```python
# tests/unit/domain/test_query_validator.py
import pytest
from app.domain.analytics.services import QueryValidator
from app.domain.analytics.exceptions import UnsafeQueryError

def test_rejects_delete_statement():
    validator = QueryValidator()
    with pytest.raises(UnsafeQueryError):
        validator.validate("DELETE FROM orders")

def test_allows_select():
    validator = QueryValidator()
    validator.validate("SELECT * FROM orders LIMIT 10")  # should not raise
```

### Integration Tests

- Test repository implementations against a real (test) database.
- Test Claude client with recorded/mocked responses.

### E2E Tests

- Use FastAPI's `TestClient` for full round-trip HTTP tests.
- Run against a test database with seeded data.

### Running Tests

```bash
# All tests
pytest

# Unit only (fast)
pytest tests/unit -q

# Integration
pytest tests/integration

# With coverage
pytest --cov=app --cov-report=term-missing
```

---

## Conventions

### Naming

| Thing             | Convention             | Example                          |
|-------------------|------------------------|----------------------------------|
| Files             | `snake_case.py`        | `ask_question.py`                |
| Classes           | `PascalCase`           | `AskQuestionHandler`             |
| Functions/methods | `snake_case`           | `execute_query()`                |
| Constants         | `UPPER_SNAKE`          | `MAX_ROW_LIMIT`                  |
| API routes        | `kebab-case` URLs      | `/api/v1/ask`                    |
| Domain entities   | Nouns                  | `Query`, `Insight`               |
| Use cases         | Verb + Noun            | `AskQuestion`, `GenerateDashboard` |
| Repositories      | `{Entity}Repository`   | `AnalyticsRepository`            |
| Exceptions        | `{What}Error`          | `UnsafeQueryError`               |

### Imports

- Absolute imports from `app.` always.
- Group: stdlib → third-party → local. Separated by blank lines.

### Pydantic Models

- **Domain entities:** Use `dataclasses` or plain Pydantic `BaseModel` with no ORM coupling.
- **DTOs (application layer):** Pydantic `BaseModel` — these are the command/query/response shapes.
- **API schemas (interface layer):** Can reuse application DTOs or define separate request/response models if the shape differs.

### Async

- Use `async def` for all IO-bound operations (DB queries, API calls).
- Use `def` (sync) for pure domain logic — no need for async overhead.
- FastAPI handles both seamlessly.

### Git

- Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`
- One concern per commit.
- Feature branches off `main`, merged via PR.
