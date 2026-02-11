import re
import duckdb
from app.config import settings

_conn: duckdb.DuckDBPyConnection | None = None

BLOCKED_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|MERGE|GRANT|REVOKE|EXEC|EXECUTE|CALL)\b",
    re.IGNORECASE,
)


def connect() -> duckdb.DuckDBPyConnection:
    global _conn
    _conn = duckdb.connect(f"md:?motherduck_token={settings.motherduck_token}")
    _conn.execute(f'USE "{settings.motherduck_database}"')
    return _conn


def get_connection() -> duckdb.DuckDBPyConnection:
    if _conn is None:
        raise RuntimeError("Database not connected. Call connect() first.")
    return _conn


def close():
    global _conn
    if _conn:
        _conn.close()
        _conn = None


def execute_read_query(sql: str) -> tuple[list[str], list[list]]:
    """Execute a read-only query. Returns (columns, rows).

    Raises ValueError if the query is not a SELECT/WITH statement
    or contains blocked DML/DDL keywords.
    """
    stripped = sql.strip().rstrip(";").strip()

    if not re.match(r"^(SELECT|WITH)\b", stripped, re.IGNORECASE):
        raise ValueError("Only SELECT and WITH statements are allowed.")

    if BLOCKED_KEYWORDS.search(stripped):
        raise ValueError("Query contains blocked keywords.")

    conn = get_connection()
    result = conn.execute(stripped)
    columns = [desc[0] for desc in result.description]
    rows = result.fetchmany(settings.row_limit)
    return columns, [list(row) for row in rows]
