import re
from app.database import get_connection
from app.config import settings
from app.question_parser import set_product_stems, set_location_names

_schema_context: str = ""
_data_dictionary: str = ""
_table_count: int = 0
_product_catalog: str = ""

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


# munu is always included; extra schemas come from config (EXTRA_SCHEMAS env var)
_INCLUDED_SCHEMAS = {"munu"} | {s.strip() for s in settings.extra_schemas.split(",") if s.strip()}
# Internal/ETL tables to hide from the LLM
_EXCLUDED_TABLES = {"_etl_state", "test_write"}


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
    # Track raw column names per table for relationship discovery
    table_columns: dict[str, list[str]] = {}
    for schema, table, column, dtype in rows:
        # Filter to restaurant-relevant schemas only
        if schema not in _INCLUDED_SCHEMAS:
            continue
        if table in _EXCLUDED_TABLES:
            continue
        key = f"{schema}.{table}" if schema != "main" else table
        if key not in tables:
            tables[key] = []
            table_columns[key] = []
        tables[key].append(f"{column}:{_short_type(dtype)}")
        table_columns[key].append(column)

    _table_count = len(tables)

    # Compact format: TABLE_NAME(col1:TYPE, col2:TYPE, ...)
    lines = ["SCHEMA:"]
    for table_name, columns in tables.items():
        lines.append(f"{table_name}({', '.join(columns)})")

    # Auto-discover join relationships from _id columns
    joins = _discover_relationships(table_columns)
    if joins:
        lines.append("\nJOINS (use these when you need data from related tables):")
        for join in joins:
            lines.append(join)

    _schema_context = "\n".join(lines)
    return _schema_context


def _discover_relationships(table_columns: dict[str, list[str]]) -> list[str]:
    """Find FK-like relationships by matching *_id columns to other tables."""
    # Build lookup: bare table name → full qualified name
    # e.g. "outlets" → "munu.outlets", "articles" → "munu.articles"
    bare_to_full: dict[str, str] = {}
    for full_name in table_columns:
        bare = full_name.split(".")[-1]
        bare_to_full[bare] = full_name

    joins = []
    for full_table, columns in table_columns.items():
        for col in columns:
            if not col.endswith("_id"):
                continue
            # e.g. "outlet_id" → try "outlets", "outlet"
            base = col[:-3]  # strip "_id"
            candidates = [base + "s", base, base + "es"]
            for candidate in candidates:
                target_full = bare_to_full.get(candidate)
                if target_full and target_full != full_table:
                    # Check target has "id" column
                    if "id" in table_columns[target_full]:
                        joins.append(f"{full_table}.{col} → {target_full}.id")
                    break
    return joins


def precrunch_metadata() -> str:
    """Query live DB at startup to build a rich data dictionary for the LLM.

    Discovers: locations, date ranges, row counts, categories, payment types.
    Runs once — results are cached in _data_dictionary.
    """
    global _data_dictionary
    conn = get_connection()
    lines = ["DATA DICTIONARY:"]

    def _safe_query(sql: str):
        try:
            return conn.execute(sql).fetchall()
        except Exception:
            return []

    # --- Locations (revenue_units is the correct location table; orders.inid is empty) ---
    rows = _safe_query("SELECT DISTINCT name FROM munu.revenue_units WHERE name IS NOT NULL ORDER BY name")
    if rows:
        names = [r[0] for r in rows]
        set_location_names(names)
        lines.append(f"Locations ({len(names)}): {', '.join(names)}")
        lines.append("  -> Table: munu.revenue_units (customer_id, revenue_unit_id, name)")
        lines.append("  -> Join from orders: o.customer_id = ru.customer_id AND o.revenue_unit_id = ru.revenue_unit_id")
        lines.append("  -> WARNING: Do NOT use munu.installations for location — orders.inid is always empty")

    # --- Date range ---
    rows = _safe_query("SELECT MIN(order_date), MAX(order_date), COUNT(*) FROM munu.orders")
    if rows and rows[0][0]:
        min_d, max_d, count = rows[0]
        lines.append(f"Orders: {count:,} rows, dates {min_d} to {max_d}")

    rows = _safe_query("SELECT COUNT(*) FROM munu.order_lines")
    if rows:
        lines.append(f"Order lines: {rows[0][0]:,} rows")

    # --- Categories ---
    rows = _safe_query(
        "SELECT DISTINCT article_group_name FROM munu.articles "
        "WHERE article_group_name IS NOT NULL ORDER BY article_group_name"
    )
    if rows:
        cats = [r[0] for r in rows]
        lines.append(f"Product categories ({len(cats)}): {', '.join(cats)}")

    # --- Payment types ---
    rows = _safe_query("SELECT DISTINCT name FROM munu.payment_types WHERE name IS NOT NULL ORDER BY name")
    if rows:
        pts = [r[0] for r in rows]
        lines.append(f"Payment types: {', '.join(pts)}")

    # --- Revenue units ---
    rows = _safe_query("SELECT DISTINCT name FROM munu.revenue_units WHERE name IS NOT NULL ORDER BY name")
    if rows:
        rus = [r[0] for r in rows]
        lines.append(f"Revenue units: {', '.join(rus)}")

    # --- Planday departments (if available) ---
    rows = _safe_query("SELECT DISTINCT name FROM planday.departments WHERE name IS NOT NULL ORDER BY name")
    if rows:
        depts = [r[0] for r in rows]
        lines.append(f"Planday departments: {', '.join(depts)}")

    _data_dictionary = "\n".join(lines)
    print(f"Pre-crunched data dictionary: {len(lines)-1} entries")
    return _data_dictionary


def get_schema_context() -> str:
    parts = [_schema_context]
    if _data_dictionary:
        parts.append(_data_dictionary)
    if _product_catalog:
        parts.append(_product_catalog)
    return "\n\n".join(parts)


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
        if schema not in _INCLUDED_SCHEMAS:
            continue
        if table in _EXCLUDED_TABLES:
            continue
        key = f"{schema}.{table}" if schema != "main" else table
        if key not in tables:
            tables[key] = []
        tables[key].append({
            "column": column,
            "type": dtype,
            "nullable": nullable == "YES",
        })

    return {"tables": tables, "table_count": len(tables)}


# --- Product catalog ---

# Prefixes to strip: leading digits (optionally with letters), 1-3 char uppercase codes
_PREFIX_RE = re.compile(r"^(?:\d+[A-Za-z]*\s*|[A-Z]{1,3}\s+)")
# Suffixes to strip: trailing single char, common POS suffixes
_SUFFIX_RE = re.compile(r"(?:\s+(?:steam|web|spesialpris|krans|s)|\s+[A-Za-z])$", re.IGNORECASE)


def _normalize(name: str) -> str:
    """Normalize a product name for grouping: strip prefixes/suffixes, lowercase."""
    n = _PREFIX_RE.sub("", name).strip()
    n = _SUFFIX_RE.sub("", n).strip()
    return n.lower()


def build_product_catalog() -> str:
    """Build a grouped product catalog from munu.articles for LLM context."""
    global _product_catalog

    conn = get_connection()
    try:
        result = conn.execute("SELECT DISTINCT name FROM munu.articles ORDER BY name")
        names = [row[0] for row in result.fetchall() if row[0]]
    except Exception as e:
        print(f"Warning: Could not build product catalog: {e}")
        _product_catalog = ""
        return _product_catalog

    if not names:
        _product_catalog = ""
        return _product_catalog

    # Build (normalized, original) pairs and sort by normalized
    pairs = [(_normalize(n), n) for n in names]
    pairs.sort(key=lambda p: p[0])

    # Group consecutive names sharing a common prefix of 5+ chars
    groups: list[list[str]] = []
    current_stem = ""
    current_group: list[str] = []

    for norm, orig in pairs:
        if current_stem and norm[:5] == current_stem[:5] and len(norm) >= 5:
            current_group.append(orig)
        else:
            if current_group:
                groups.append(current_group)
            current_stem = norm
            current_group = [orig]

    if current_group:
        groups.append(current_group)

    # Collect all stems (including single-variant products)
    all_stems: list[str] = []
    group_count = 0
    for group in groups:
        stem = _normalize(group[0])
        if len(stem) >= 5:
            all_stems.append(stem[:12].rstrip())
        if len(group) >= 2:
            group_count += 1

    if not all_stems:
        _product_catalog = ""
        return _product_catalog

    # Compact format: just list the stems, not every variant
    _product_catalog = (
        f"PRODUCTS ({len(names)} articles, {len(all_stems)} searchable stems):\n"
        f"Match with: ol.article_name ILIKE '%<stem>%'\n"
        f"Stems: {', '.join(sorted(set(all_stems)))}"
    )
    print(f"Built product catalog: {len(all_stems)} stems from {len(names)} articles")

    # Feed all stems to question parser for entity extraction
    stem_list = list({_normalize(g[0])[:5] for g in groups if len(_normalize(g[0])) >= 5})
    set_product_stems(stem_list)

    return _product_catalog


def get_product_catalog() -> str:
    return _product_catalog
