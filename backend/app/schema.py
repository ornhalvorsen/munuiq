from app.database import get_connection

_schema_context: str = ""
_table_count: int = 0

# Shorten verbose DuckDB type names to save tokens
_TYPE_MAP = {
    "BIGINT": "INT",
    "INTEGER": "INT",
    "SMALLINT": "INT",
    "TINYINT": "INT",
    "HUGEINT": "INT",
    "DOUBLE": "FLOAT",
    "FLOAT": "FLOAT",
    "DECIMAL": "DEC",
    "VARCHAR": "STR",
    "TEXT": "STR",
    "BOOLEAN": "BOOL",
    "TIMESTAMP WITH TIME ZONE": "TSTZ",
    "TIMESTAMP": "TS",
    "DATE": "DATE",
    "TIME": "TIME",
    "BLOB": "BLOB",
}


def _short_type(dtype: str) -> str:
    upper = dtype.upper()
    for k, v in _TYPE_MAP.items():
        if upper.startswith(k):
            return v
    return dtype[:8]


def discover_schema() -> str:
    """Query information_schema.columns and build a compact text description."""
    global _schema_context, _table_count

    conn = get_connection()
    result = conn.execute("""
        SELECT table_schema, table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
        ORDER BY table_schema, table_name, ordinal_position
    """)
    rows = result.fetchall()

    tables: dict[str, list[str]] = {}
    for schema, table, column, dtype in rows:
        key = f"{schema}.{table}" if schema != "main" else table
        if key not in tables:
            tables[key] = []
        tables[key].append(f"{column}:{_short_type(dtype)}")

    _table_count = len(tables)

    # Compact format: TABLE_NAME(col1:TYPE, col2:TYPE, ...)
    lines = ["SCHEMA:"]
    for table_name, columns in tables.items():
        lines.append(f"{table_name}({', '.join(columns)})")

    _schema_context = "\n".join(lines)
    return _schema_context


def get_schema_context() -> str:
    return _schema_context


def get_table_count() -> int:
    return _table_count


def get_schema_dict() -> dict:
    """Return schema as structured dict for the /api/schema endpoint."""
    conn = get_connection()
    result = conn.execute("""
        SELECT table_schema, table_name, column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
        ORDER BY table_schema, table_name, ordinal_position
    """)
    rows = result.fetchall()

    tables: dict[str, list[dict]] = {}
    for schema, table, column, dtype, nullable in rows:
        key = f"{schema}.{table}" if schema != "main" else table
        if key not in tables:
            tables[key] = []
        tables[key].append({
            "column": column,
            "type": dtype,
            "nullable": nullable == "YES",
        })

    return {"tables": tables, "table_count": len(tables)}
