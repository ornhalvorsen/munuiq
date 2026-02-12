# AnalyticsIQ Development Guide

> Setup, workflow, and day-to-day conventions.

---

## Prerequisites

- Python 3.12+
- Node.js 20+
- A MotherDuck account + token
- An Anthropic API key

---

## Quick Start

### Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your actual keys

# Run dev server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

npm install
npm run dev
# Runs on http://localhost:5173, proxies /api to :8000
```

---

## Development Workflow

### Adding a New Feature (End-to-End)

Follow the DDD layers from inside out:

1. **Domain** — Define entities, value objects, exceptions, repository ABCs.
2. **Application** — Create use case handler + DTOs.
3. **Infrastructure** — Implement repository, external clients.
4. **Interfaces** — Add API route, wire up dependencies.
5. **Tests** — Unit tests for domain + application, integration for infrastructure.

### Example: Adding a "Favorites" Feature

```
1. domain/favorites/
   ├── entities.py          → Favorite(user_id, query_text, created_at)
   ├── repositories.py      → ABC: FavoritesRepository
   └── exceptions.py        → FavoriteNotFoundError

2. application/favorites/
   ├── save_favorite.py     → SaveFavoriteHandler.execute(command)
   ├── list_favorites.py    → ListFavoritesHandler.execute(query)
   └── dtos.py              → SaveFavoriteCommand, FavoriteDTO

3. infrastructure/database/repositories/
   └── favorites_repo.py    → DuckDBFavoritesRepository implements ABC

4. interfaces/api/v1/
   └── favorites.py         → POST /favorites, GET /favorites

5. tests/
   ├── unit/domain/test_favorite_entity.py
   ├── unit/application/test_save_favorite.py
   └── integration/test_favorites_repo.py
```

---

## Code Style

### Python

- Format with **Ruff** (replaces black + isort + flake8):

```bash
# Format
ruff format .

# Lint
ruff check .

# Fix auto-fixable issues
ruff check --fix .
```

- Type hints on all public functions.
- Docstrings only where the purpose isn't obvious from the name.

### TypeScript

- Format with **Prettier** + lint with **ESLint** (already configured).
- Strict mode enabled in `tsconfig.json`.

---

## Environment Variables

| Variable              | Required | Default                          | Description                   |
|-----------------------|----------|----------------------------------|-------------------------------|
| `ANTHROPIC_API_KEY`   | Yes      | —                                | Claude API key                |
| `MOTHERDUCK_TOKEN`    | Yes      | —                                | MotherDuck auth token         |
| `MOTHERDUCK_DATABASE` | No       | `Kanelsnurren`                   | Database name                 |
| `CLAUDE_MODEL`        | No       | `claude-sonnet-4-5-20250929`     | Model ID for SQL generation   |
| `ROW_LIMIT`           | No       | `500`                            | Max rows per query            |
| `JWT_SECRET`          | Yes*     | —                                | JWT signing secret            |
| `APP_ENV`             | No       | `development`                    | `development` / `production`  |
| `DEBUG`               | No       | `false`                          | Enable debug mode             |
| `ALLOWED_ORIGINS`     | No       | `["http://localhost:5173"]`      | CORS allowed origins (JSON)   |
| `RATE_LIMIT_PER_MINUTE` | No    | `60`                             | Global rate limit             |

*Required in production. Can be empty in development if auth is disabled.

---

## Project Conventions

### File Organization Rules

- **One bounded context = one folder** in each layer.
- **One use case = one file** in the application layer.
- **One router = one bounded context** in the interface layer.
- Repository interfaces live in `domain/`, implementations in `infrastructure/database/repositories/`.

### Dependency Direction

```
interfaces/ → application/ → domain/
                  ↑
          infrastructure/
```

Infrastructure implements domain interfaces but is injected by the interface layer via FastAPI `Depends()`.

### When to Create a New Bounded Context

Ask: "Does this concept have its own lifecycle, its own rules, and its own vocabulary?"

- If yes → new bounded context (new folder in `domain/`, `application/`, etc.)
- If no → it probably belongs in an existing context or in `shared/`.

### Naming Files

| Layer          | File Name Pattern       | Example                       |
|----------------|-------------------------|-------------------------------|
| Domain         | `entities.py`           | `domain/analytics/entities.py` |
| Domain         | `services.py`           | `domain/analytics/services.py` |
| Domain         | `repositories.py`       | `domain/analytics/repositories.py` |
| Application    | `{verb}_{noun}.py`      | `application/analytics/ask_question.py` |
| Application    | `dtos.py`               | `application/analytics/dtos.py` |
| Infrastructure | `{context}_repo.py`     | `infrastructure/database/repositories/analytics_repo.py` |
| Interfaces     | `{context}.py`          | `interfaces/api/v1/analytics.py` |

---

## Testing

### Run Tests

```bash
# All tests
pytest

# Specific layer
pytest tests/unit/domain -v
pytest tests/integration -v

# Single test file
pytest tests/unit/domain/test_query_validator.py -v

# With coverage
pytest --cov=app --cov-report=term-missing
```

### Test Fixtures

Shared fixtures go in `tests/conftest.py`. Layer-specific fixtures go in that layer's conftest:

```
tests/
├── conftest.py                    # Settings, test DB connection
├── unit/
│   ├── conftest.py               # Mock factories
│   └── domain/
│       └── test_query_validator.py
└── integration/
    ├── conftest.py               # Real DB setup/teardown
    └── infrastructure/
        └── test_analytics_repo.py
```

### Writing Good Tests

- Test **behavior**, not implementation details.
- One assertion per test (or one logical assertion group).
- Use descriptive names: `test_rejects_delete_statement`, not `test_validator_1`.
- Domain tests must have zero IO — they should run without any network or database.

---

## Troubleshooting

### Common Issues

**MotherDuck connection fails:**
- Check `MOTHERDUCK_TOKEN` is set and valid.
- Verify network connectivity to MotherDuck.

**Claude API errors:**
- Check `ANTHROPIC_API_KEY` is valid.
- Check rate limits on your Anthropic account.

**CORS errors in browser:**
- Ensure `ALLOWED_ORIGINS` includes your frontend URL.
- Check that the Vite proxy in `vite.config.ts` is configured correctly.

**Import errors after restructuring:**
- All imports must be absolute from `app.` (e.g., `from app.domain.analytics.entities import Query`).
- Check `__init__.py` files exist in every package directory.
