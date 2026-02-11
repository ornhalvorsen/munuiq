"""
Separate MotherDuck connection for interaction logging.

Uses MOTHERDUCK_LOGGING_TOKEN (read-write) and stores data in the
'munuiq' database — completely isolated from the read-only restaurant DB.
All writes are wrapped in try/except so logging never breaks the main flow.
"""

import json
import threading
import duckdb
from app.config import settings

_conn: duckdb.DuckDBPyConnection | None = None
_lock = threading.Lock()

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS interactions (
    interaction_id  VARCHAR PRIMARY KEY,
    created_at      TIMESTAMP DEFAULT current_timestamp,
    question        VARCHAR,
    model           VARCHAR,
    provider        VARCHAR,
    generated_sql   VARCHAR,
    query_succeeded BOOLEAN,
    error_message   VARCHAR,
    columns         VARCHAR,          -- JSON array
    row_count       INTEGER,
    insight         VARCHAR,
    chart_type      VARCHAR,
    sql_time_ms     INTEGER,
    insight_time_ms INTEGER,
    query_time_ms   INTEGER,
    feedback        VARCHAR,          -- 'up' | 'down' | NULL
    matched_products VARCHAR,         -- JSON array of matched product stems
    time_period     VARCHAR           -- extracted time period or NULL
);
"""

_CREATE_SQL_FIXES_TABLE = """
CREATE TABLE IF NOT EXISTS sql_fixes (
    id              INTEGER PRIMARY KEY DEFAULT nextval('sql_fixes_seq'),
    created_at      TIMESTAMP DEFAULT current_timestamp,
    question        VARCHAR,
    model           VARCHAR,
    original_sql    VARCHAR,
    error           VARCHAR,
    fixed_sql       VARCHAR
);
"""


def connect():
    """Open a writable MotherDuck connection and ensure the table exists."""
    global _conn
    token = settings.motherduck_logging_token or settings.motherduck_token
    if not token:
        print("Logging DB: no token configured — logging disabled.")
        return
    try:
        _conn = duckdb.connect(f"md:?motherduck_token={token}")
        _conn.execute(f'CREATE DATABASE IF NOT EXISTS "{settings.motherduck_logging_database}"')
        _conn.execute(f'USE "{settings.motherduck_logging_database}"')
        _conn.execute(_CREATE_TABLE)
        # sql_fixes table for learning from corrections
        try:
            _conn.execute("CREATE SEQUENCE IF NOT EXISTS sql_fixes_seq START 1")
        except Exception:
            pass
        _conn.execute(_CREATE_SQL_FIXES_TABLE)
        # Add columns if upgrading from older schema
        for col, dtype in [("matched_products", "VARCHAR"), ("time_period", "VARCHAR")]:
            try:
                _conn.execute(f"ALTER TABLE interactions ADD COLUMN {col} {dtype}")
            except Exception:
                pass  # column already exists
        print("Logging DB connected.")
    except Exception as e:
        print(f"Logging DB: connection failed — {e}")
        _conn = None


def close():
    global _conn
    if _conn:
        try:
            _conn.close()
        except Exception:
            pass
        _conn = None


def log_interaction(
    *,
    interaction_id: str,
    question: str,
    model: str,
    provider: str,
    generated_sql: str,
    query_succeeded: bool,
    error_message: str | None = None,
    columns: list[str] | None = None,
    row_count: int | None = None,
    insight: str | None = None,
    chart_type: str | None = None,
    sql_time_ms: int | None = None,
    insight_time_ms: int | None = None,
    query_time_ms: int | None = None,
    matched_products: list[str] | None = None,
    time_period: str | None = None,
) -> None:
    """Insert one interaction row. Fails silently."""
    if _conn is None:
        return
    try:
        cols_json = json.dumps(columns) if columns else None
        products_json = json.dumps(matched_products) if matched_products else None
        with _lock:
            _conn.execute(
                """
                INSERT INTO interactions (
                    interaction_id, question, model, provider,
                    generated_sql, query_succeeded, error_message,
                    columns, row_count, insight, chart_type,
                    sql_time_ms, insight_time_ms, query_time_ms,
                    matched_products, time_period
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    interaction_id, question, model, provider,
                    generated_sql, query_succeeded, error_message,
                    cols_json, row_count, insight, chart_type,
                    sql_time_ms, insight_time_ms, query_time_ms,
                    products_json, time_period,
                ],
            )
    except Exception as e:
        print(f"Logging DB: failed to log interaction — {e}")


def update_feedback(interaction_id: str, feedback: str) -> bool:
    """Set feedback ('up'/'down') on an interaction. Returns True on success."""
    if _conn is None:
        return False
    try:
        with _lock:
            result = _conn.execute(
                "UPDATE interactions SET feedback = ? WHERE interaction_id = ?",
                [feedback, interaction_id],
            )
            return result.fetchone() is not None or True
    except Exception as e:
        print(f"Logging DB: failed to update feedback — {e}")
        return False


def export_training_pairs() -> list[dict]:
    """Return successful, thumbs-up interactions as training pairs."""
    if _conn is None:
        return []
    try:
        result = _conn.execute(
            """
            SELECT question, generated_sql, model, provider, created_at,
                   matched_products, time_period
            FROM interactions
            WHERE query_succeeded = true AND feedback = 'up'
            ORDER BY created_at DESC
            """
        )
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        print(f"Logging DB: failed to export — {e}")
        return []


def log_sql_fix(
    *,
    question: str,
    model: str,
    original_sql: str,
    error: str,
    fixed_sql: str,
) -> None:
    """Log a successful SQL correction for pattern learning. Fails silently."""
    if _conn is None:
        return
    try:
        with _lock:
            _conn.execute(
                """
                INSERT INTO sql_fixes (question, model, original_sql, error, fixed_sql)
                VALUES (?, ?, ?, ?, ?)
                """,
                [question, model, original_sql, error, fixed_sql],
            )
    except Exception as e:
        print(f"Logging DB: failed to log SQL fix — {e}")


def export_sql_fixes() -> list[dict]:
    """Return all logged SQL corrections for analysis."""
    if _conn is None:
        return []
    try:
        result = _conn.execute(
            """
            SELECT question, model, original_sql, error, fixed_sql, created_at
            FROM sql_fixes
            ORDER BY created_at DESC
            """
        )
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        print(f"Logging DB: failed to export SQL fixes — {e}")
        return []
