# AnalyticsIQ Security Guide

> Security patterns and requirements for the AnalyticsIQ platform.

---

## Table of Contents

1. [Security Principles](#security-principles)
2. [Authentication & Authorization](#authentication--authorization)
3. [Input Validation & Sanitization](#input-validation--sanitization)
4. [SQL Injection Prevention](#sql-injection-prevention)
5. [API Security](#api-security)
6. [Secrets Management](#secrets-management)
7. [CORS & Headers](#cors--headers)
8. [Rate Limiting](#rate-limiting)
9. [Logging & Monitoring](#logging--monitoring)
10. [Dependency Security](#dependency-security)
11. [Deployment Security](#deployment-security)

---

## Security Principles

1. **Defense in depth** — Multiple layers of protection. Never rely on a single control.
2. **Least privilege** — Every component gets the minimum access it needs.
3. **Validate at the boundary** — All external input is untrusted. Validate on entry, not deep inside.
4. **Fail securely** — Errors must not leak internal state. Default to deny.
5. **Security is not a layer** — It's woven into every layer of the DDD architecture.

---

## Authentication & Authorization

### JWT-Based Auth

```python
# app/infrastructure/security/auth.py
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from app.config import Settings

security = HTTPBearer()

class AuthService:
    def __init__(self, settings: Settings):
        self._secret = settings.jwt_secret
        self._algorithm = settings.jwt_algorithm

    def create_token(self, user_id: str, roles: list[str]) -> str:
        payload = {
            "sub": user_id,
            "roles": roles,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=8),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def verify_token(self, token: str) -> dict:
        try:
            return jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
```

### Route Protection

```python
# Use as a FastAPI dependency on protected routes
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth: AuthService = Depends(get_auth_service),
) -> dict:
    return auth.verify_token(credentials.credentials)

# In router:
@router.get("/protected")
async def protected_route(user: dict = Depends(get_current_user)):
    ...
```

### Authorization Rules

- **Public:** `GET /api/v1/health`
- **Authenticated:** All other endpoints require a valid JWT.
- **Role-based:** Admin endpoints check `"admin" in user["roles"]`.
- Never check permissions inside domain logic — handle it at the interface/middleware layer.

---

## Input Validation & Sanitization

### Pydantic as First Line of Defense

Every API input goes through a Pydantic model. This gives you type checking, length limits, and pattern validation for free.

```python
# app/application/analytics/dtos.py
from pydantic import BaseModel, Field, field_validator
import re

class AskQuestionCommand(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Natural language question about restaurant data",
    )

    @field_validator("question")
    @classmethod
    def sanitize_question(cls, v: str) -> str:
        # Strip control characters
        v = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", v)
        return v.strip()
```

### Rules

- Define `min_length`, `max_length` on all string fields.
- Use `Field(pattern=...)` for structured inputs (emails, IDs, etc.).
- Use `field_validator` for custom sanitization logic.
- Never pass raw user input to SQL, shell commands, or template engines.

---

## SQL Injection Prevention

This is the **highest-risk area** in AnalyticsIQ because the system generates SQL from natural language. Multiple defenses are required.

### Layer 1: Domain-Level SQL Validation

```python
# app/domain/analytics/services.py
import re

class QueryValidator:
    """Domain service — validates generated SQL before execution."""

    BLOCKED_KEYWORDS = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
        "TRUNCATE", "GRANT", "REVOKE", "EXEC", "EXECUTE",
        "ATTACH", "DETACH", "COPY", "LOAD", "INSTALL",
    ]

    def validate(self, sql: str) -> None:
        upper = sql.upper().strip()

        # Must start with SELECT or WITH
        if not re.match(r"^\s*(SELECT|WITH)\b", upper):
            raise UnsafeQueryError(f"Query must start with SELECT or WITH")

        # Block dangerous keywords
        for keyword in self.BLOCKED_KEYWORDS:
            # Word boundary check to avoid false positives
            if re.search(rf"\b{keyword}\b", upper):
                raise UnsafeQueryError(f"Blocked keyword detected: {keyword}")

        # Block multiple statements (semicolons followed by more SQL)
        if re.search(r";\s*\S", sql):
            raise UnsafeQueryError("Multiple statements not allowed")
```

### Layer 2: Database-Level Restrictions

```python
# app/infrastructure/database/connection.py

# Use a READ-ONLY database connection/user where possible.
# With MotherDuck, use share tokens with read-only access.

async def execute_safe_query(conn, sql: str, row_limit: int = 500):
    """Execute with a hard row limit to prevent resource exhaustion."""
    limited_sql = f"SELECT * FROM ({sql}) AS _q LIMIT {row_limit}"
    return conn.execute(limited_sql).fetchdf()
```

### Layer 3: Claude Prompt Engineering

Include explicit safety instructions in the system prompt sent to Claude:

```
You MUST ONLY generate SELECT or WITH...SELECT statements.
NEVER generate INSERT, UPDATE, DELETE, DROP, ALTER, or any DDL/DML.
NEVER use semicolons to chain multiple statements.
If the user's question cannot be answered with a read-only query, respond with an error explanation.
```

### Summary: Three Independent Barriers

1. **Prompt engineering** — Claude is instructed to only generate safe SQL.
2. **Domain validation** — `QueryValidator` rejects anything that isn't a pure read query.
3. **DB-level enforcement** — Read-only credentials + row limits.

An attacker would need to bypass all three simultaneously.

---

## API Security

### Request Size Limits

```python
# In main.py or middleware
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    MAX_BODY_SIZE = 1_048_576  # 1 MB

    async def dispatch(self, request: Request, call_next):
        if request.headers.get("content-length"):
            if int(request.headers["content-length"]) > self.MAX_BODY_SIZE:
                return JSONResponse(status_code=413, content={"error": "Request too large"})
        return await call_next(request)
```

### API Versioning

- All endpoints live under `/api/v1/`.
- When breaking changes are needed, create `/api/v2/` and deprecate v1 with a timeline.
- Never break v1 silently.

### Response Hygiene

- Never return raw database errors to clients.
- Never include stack traces in production responses.
- Strip internal IDs, connection strings, and system paths from error messages.

```python
# In the unhandled exception handler:
@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception", exc_info=exc)  # Log full details
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},  # Generic to client
    )
```

---

## Secrets Management

### Rules

1. **Never commit secrets.** Use `.env` files (gitignored) or environment variables.
2. **Validate on startup.** If a required secret is missing, fail immediately — don't start the server.
3. **No secrets in logs.** Redact API keys, tokens, and passwords from all log output.
4. **Rotate regularly.** JWT secrets, API keys, and DB credentials should be rotatable without downtime.

### .env.example

Commit a `.env.example` with placeholder values so developers know what's needed:

```env
# Required
ANTHROPIC_API_KEY=sk-ant-...
MOTHERDUCK_TOKEN=your-token-here
JWT_SECRET=generate-a-strong-random-string

# Optional
MOTHERDUCK_DATABASE=Kanelsnurren
CLAUDE_MODEL=claude-sonnet-4-5-20250929
APP_ENV=development
DEBUG=true
```

### .gitignore

Ensure these are always ignored:

```
.env
.env.local
.env.production
*.pem
*.key
```

---

## CORS & Headers

### CORS Configuration

```python
# app/interfaces/middleware/cors.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

def configure_cors(app: FastAPI):
    from app.config import Settings
    settings = Settings()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,  # Explicit list, never ["*"] in production
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,  # Cache preflight for 10 minutes
    )
```

### Security Headers

```python
# app/interfaces/middleware/security_headers.py
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response
```

---

## Rate Limiting

Protect against abuse and resource exhaustion — especially important since each `/ask` request triggers Claude API calls.

```python
# app/infrastructure/security/rate_limiter.py
import time
from collections import defaultdict
from fastapi import Request, HTTPException, status

class InMemoryRateLimiter:
    """Simple token-bucket rate limiter. Replace with Redis for multi-process."""

    def __init__(self, requests_per_minute: int = 60):
        self._rpm = requests_per_minute
        self._window = 60.0
        self._requests: dict[str, list[float]] = defaultdict(list)

    def check(self, client_id: str) -> None:
        now = time.time()
        window_start = now - self._window

        # Prune old entries
        self._requests[client_id] = [
            t for t in self._requests[client_id] if t > window_start
        ]

        if len(self._requests[client_id]) >= self._rpm:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Try again later.",
            )

        self._requests[client_id].append(now)
```

### Per-Endpoint Limits

Apply stricter limits to expensive operations:

| Endpoint              | Limit           | Reason                    |
|-----------------------|-----------------|---------------------------|
| `POST /api/v1/ask`   | 10/min per user | Each call invokes Claude   |
| `GET /api/v1/dashboard` | 30/min       | Heavy computation          |
| `GET /api/v1/schema` | 60/min          | Lightweight, cacheable     |

---

## Logging & Monitoring

### Structured Logging

```python
# app/interfaces/middleware/request_logging.py
import logging
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("munuiq")

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start = time.time()

        response = await call_next(request)

        duration_ms = (time.time() - start) * 1000
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(duration_ms, 1),
                "client": request.client.host if request.client else "unknown",
            },
        )

        response.headers["X-Request-ID"] = request_id
        return response
```

### What to Log

- All requests: method, path, status, duration, client IP.
- Authentication failures: token, IP, timestamp.
- SQL validation rejections: the blocked query (for security monitoring).
- Unhandled exceptions: full traceback (server-side only).

### What NOT to Log

- API keys, tokens, passwords.
- Full request/response bodies (can contain PII).
- User questions (unless consent is given — may contain sensitive restaurant data).

---

## Dependency Security

### Python

```bash
# Audit dependencies for known vulnerabilities
pip audit

# Pin all dependencies in requirements.txt with exact versions
pip freeze > requirements.txt

# Keep dependencies updated
pip install --upgrade pip-audit
```

### Node.js (Frontend)

```bash
# Audit for vulnerabilities
npm audit

# Fix automatically where possible
npm audit fix

# Use lockfile
# Always commit package-lock.json
```

### Rules

- Review new dependencies before adding them. Prefer well-maintained, widely-used packages.
- Run `pip audit` / `npm audit` in CI.
- Update dependencies at least monthly.

---

## Deployment Security

### Checklist

- [ ] `DEBUG=false` in production.
- [ ] `allowed_origins` is set to actual production domains (not `*`).
- [ ] JWT secret is a strong random string (min 32 characters).
- [ ] Database credentials use read-only access where possible.
- [ ] HTTPS is enforced (redirect HTTP → HTTPS).
- [ ] API docs (`/api/docs`, `/api/redoc`) are disabled or auth-protected in production.
- [ ] Environment variables are set via platform secrets (not `.env` files on the server).
- [ ] Container runs as non-root user.
- [ ] No unnecessary ports are exposed.

### Production FastAPI Config

```python
def create_app() -> FastAPI:
    settings = Settings()

    app = FastAPI(
        title="AnalyticsIQ API",
        version="1.0.0",
        # Disable docs in production
        docs_url="/api/docs" if settings.debug else None,
        redoc_url="/api/redoc" if settings.debug else None,
        openapi_url="/api/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )
    ...
```
