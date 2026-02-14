"""
MotherDuck connection for the analytics schema.

Uses the main motherduck_token (R/W) to read source tables and write
analytics cubes in the same database — no cross-DB issues.
"""

import threading
import duckdb
from app.config import settings

_conn: duckdb.DuckDBPyConnection | None = None
_lock = threading.Lock()

# Source tables live in the same database — no cross-DB prefix needed
SOURCE_DB = ""
TARGET_SCHEMA = "analytics"


def connect() -> duckdb.DuckDBPyConnection | None:
    """Open R/W MotherDuck connection to the KS2 database and ensure analytics schema."""
    global _conn
    token = settings.motherduck_token
    if not token:
        print("Analytics: no token configured — analytics disabled.")
        return None
    try:
        _conn = duckdb.connect(f"md:?motherduck_token={token}")
        db = settings.motherduck_database  # "KS2-Service Agent Read"
        _conn.execute(f'USE "{db}"')
        try:
            _conn.execute(f"CREATE SCHEMA IF NOT EXISTS {TARGET_SCHEMA}")
        except Exception as e:
            if "read-only" in str(e).lower():
                print(f"Analytics: WARNING — token is read-only, cannot create schema.")
                print(f"  Discovery will work, but refresh requires a R/W token.")
            else:
                raise
        print(f"Analytics: connected to {db}.{TARGET_SCHEMA}")
        return _conn
    except Exception as e:
        print(f"Analytics: connection failed — {e}")
        _conn = None
        return None


def get_conn() -> duckdb.DuckDBPyConnection | None:
    """Return existing connection or create one."""
    if _conn is None:
        return connect()
    return _conn


def execute(sql: str, params: list = None) -> duckdb.DuckDBPyConnection:
    """Execute SQL with thread safety."""
    conn = get_conn()
    if conn is None:
        raise RuntimeError("Analytics: no database connection")
    with _lock:
        return conn.execute(sql, params or [])


def fetchall(sql: str, params: list = None) -> list[dict]:
    """Execute query and return all rows as list of dicts."""
    conn = get_conn()
    if conn is None:
        return []
    try:
        with _lock:
            result = conn.execute(sql, params or [])
            columns = [desc[0] for desc in result.description]
            rows = result.fetchall()
            return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        print(f"Analytics: query failed — {e}")
        return []


def fetchone(sql: str, params: list = None) -> dict | None:
    """Execute query and return first row as dict, or None."""
    conn = get_conn()
    if conn is None:
        return None
    try:
        with _lock:
            result = conn.execute(sql, params or [])
            columns = [desc[0] for desc in result.description]
            row = result.fetchone()
            if row is None:
                return None
            return dict(zip(columns, row))
    except Exception as e:
        print(f"Analytics: query failed — {e}")
        return None


def close():
    """Close the analytics connection."""
    global _conn
    if _conn:
        try:
            _conn.close()
        except Exception:
            pass
        _conn = None
