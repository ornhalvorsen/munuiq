"""
Analytics Refresh Orchestrator.

Manages dependency graph, executes SQL files, logs results.
Supports modes: full, incremental, backfill-groups, discover.
"""

import time
from datetime import datetime
from pathlib import Path

from app.analytics.connection import (
    execute, fetchone, get_conn, SOURCE_DB, TARGET_SCHEMA,
)
from app.analytics.discovery import has_absence_data, run_discovery


# ---------------------------------------------------------------------------
# SQL file locations
# ---------------------------------------------------------------------------
_SQL_DIR = Path(__file__).parent / "sql"


def _read_sql(relative_path: str) -> str:
    """Read a SQL file from the sql/ directory."""
    path = _SQL_DIR / relative_path
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Dependency graph — defines execution order
# ---------------------------------------------------------------------------
# Each entry: (table_name, sql_file_path, [dependencies], gated_by)
# gated_by: None or "sick_leave" (only runs if discovery found absence data)

DEPENDENCY_GRAPH = [
    # Support tables (no dependencies)
    ("config_parameters",          "support/config_parameters.sql",       [],                                       None),
    ("daypart_config",             "support/daypart_config.sql",          [],                                       None),
    ("product_group_definitions",  "support/product_group_definitions.sql", [],                                     None),
    ("refresh_log",                "support/refresh_log.sql",             [],                                       None),

    # Tier 2 — daily cubes
    ("daily_location_sales",       "tier2/daily_location_sales.sql",      [],                                       None),
    ("daily_location_product",     "tier2/daily_location_product.sql",    [],                                       None),
    ("daily_location_group_mix",   "tier2/daily_location_group_mix.sql",  ["daily_location_product", "product_group_definitions"], None),
    ("daily_fleet_group_mix",      "tier2/daily_fleet_group_mix.sql",     ["daily_location_group_mix"],              None),
    ("daily_location_daypart",     "tier2/daily_location_daypart.sql",    [],                                       None),
    ("daily_location_labor",       "tier2/daily_location_labor.sql",      ["daily_location_sales"],                  None),
    ("daily_location_labor_by_role", "tier2/daily_location_labor_by_role.sql", [],                                   None),
    ("daily_location_sick_leave",  "tier2/daily_location_sick_leave.sql", [],                                       "sick_leave"),
    ("daily_location_labor_hourly", "tier2/daily_location_labor_hourly.sql", [],                                    None),

    # Tier 3 — rolling metrics
    ("location_trailing_metrics",  "tier3/location_trailing_metrics.sql", ["daily_location_sales", "daily_location_labor"], None),
    ("location_group_mix_trailing", "tier3/location_group_mix_trailing.sql", ["daily_location_group_mix", "daily_fleet_group_mix"], None),
    ("fleet_benchmarks",           "tier3/fleet_benchmarks.sql",          ["location_trailing_metrics"],             None),
    ("daypart_benchmarks",         "tier3/daypart_benchmarks.sql",        ["daily_location_daypart"],                None),
    ("location_sick_leave_trailing", "tier3/location_sick_leave_trailing.sql", ["daily_location_sick_leave", "daily_location_labor"], "sick_leave"),
    ("location_labor_efficiency_trailing", "tier3/location_labor_efficiency_trailing.sql", ["daily_location_labor"], None),
    ("hourly_staffing_benchmarks", "tier3/hourly_staffing_benchmarks.sql", ["daily_location_labor_hourly", "config_parameters"], None),
]


# ---------------------------------------------------------------------------
# Refresh log helpers
# ---------------------------------------------------------------------------

def _log_start(table_name: str, mode: str) -> int | None:
    """Log the start of a table refresh. Returns log ID."""
    try:
        execute(f"""
            INSERT INTO {TARGET_SCHEMA}.refresh_log (id, table_name, mode, status)
            VALUES (
                (SELECT COALESCE(MAX(id), 0) + 1 FROM {TARGET_SCHEMA}.refresh_log),
                '{table_name}', '{mode}', 'running'
            )
        """)
        row = fetchone(f"""
            SELECT MAX(id) AS id FROM {TARGET_SCHEMA}.refresh_log
            WHERE table_name = '{table_name}' AND status = 'running'
        """)
        return row["id"] if row else None
    except Exception:
        return None


def _log_finish(log_id: int | None, row_count: int, status: str, error: str = None, duration_ms: int = 0):
    """Log the completion of a table refresh."""
    if log_id is None:
        return
    try:
        error_escaped = error.replace("'", "''") if error else ""
        execute(f"""
            UPDATE {TARGET_SCHEMA}.refresh_log
            SET finished_at = current_timestamp,
                duration_ms = {duration_ms},
                row_count = {row_count},
                status = '{status}',
                error_message = '{error_escaped}'
            WHERE id = {log_id}
        """)
    except Exception as e:
        print(f"  Warning: could not update refresh log — {e}")


# ---------------------------------------------------------------------------
# SQL template rendering
# ---------------------------------------------------------------------------

def _render_sql(sql: str, date_filter: str = "") -> str:
    """Replace template variables in SQL."""
    # When SOURCE_DB is empty (same-database mode), strip the prefix+dot entirely
    source_prefix = f"{SOURCE_DB}." if SOURCE_DB else ""
    return (
        sql
        .replace("{SOURCE_DB}.", source_prefix)
        .replace("{SOURCE_DB}", SOURCE_DB)
        .replace("{TARGET_SCHEMA}", TARGET_SCHEMA)
        .replace("{date_filter}", date_filter)
    )


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def _execute_sql_file(table_name: str, sql_path: str, mode: str,
                      date_filter: str = "") -> tuple[str, int, str | None]:
    """Execute a SQL file. Returns (status, row_count, error_message)."""
    sql_raw = _read_sql(sql_path)
    sql = _render_sql(sql_raw, date_filter)

    # Split multi-statement SQL (separated by semicolons)
    statements = [s.strip() for s in sql.split(";") if s.strip()]

    # Filter out comment-only blocks and placeholder markers
    statements = [
        s for s in statements
        if not s.startswith("--") or any(
            kw in s.upper() for kw in ["CREATE", "INSERT", "SELECT", "DROP", "ALTER"]
        )
    ]

    for stmt in statements:
        # Skip placeholder markers
        if stmt.strip().startswith("-- {"):
            continue
        # Skip pure comment blocks
        lines = [l.strip() for l in stmt.split("\n") if l.strip()]
        if all(l.startswith("--") for l in lines):
            continue
        execute(stmt)

    # Count rows in target table
    try:
        row = fetchone(f"SELECT COUNT(*) AS cnt FROM {TARGET_SCHEMA}.{table_name}")
        row_count = row["cnt"] if row else 0
    except Exception:
        row_count = 0

    return "completed", row_count, None


def refresh(mode: str = "full", date_from: str = None, date_to: str = None):
    """Run the analytics refresh pipeline.

    Args:
        mode: "full", "incremental", "backfill-groups", or "discover"
        date_from: For incremental mode, start date (YYYY-MM-DD)
        date_to: For incremental mode, end date (YYYY-MM-DD)
    """
    if mode == "discover":
        return run_discovery()

    conn = get_conn()
    if conn is None:
        print("Analytics: cannot refresh — no database connection")
        return

    print("=" * 60)
    print(f"ANALYTICS REFRESH — mode: {mode}")
    print(f"Started: {datetime.utcnow().isoformat()}")
    print("=" * 60)

    # Check sick leave data availability
    absence_available = has_absence_data()
    if absence_available:
        print("Discovery: absence data available — sick leave cubes will be populated")
    else:
        print("Discovery: no absence data — sick leave cubes will be created empty")

    # Build date filter for incremental mode
    date_filter = ""
    if mode == "incremental" and date_from:
        date_to_val = date_to or "CURRENT_DATE"
        if date_to:
            date_filter = f"AND o.order_date >= '{date_from}' AND o.order_date <= '{date_to}'"
        else:
            date_filter = f"AND o.order_date >= '{date_from}'"

    # Determine which tables to refresh based on mode
    if mode == "backfill-groups":
        target_tables = {
            "product_group_definitions", "daily_location_group_mix",
            "daily_fleet_group_mix", "location_group_mix_trailing",
        }
    else:
        target_tables = None  # all

    # Track completed/failed for dependency resolution
    completed = set()
    failed = set()
    skipped = set()

    total_start = time.time()

    for table_name, sql_path, deps, gate in DEPENDENCY_GRAPH:
        # Filter by mode
        if target_tables and table_name not in target_tables:
            continue

        # Check gating
        if gate == "sick_leave" and not absence_available:
            print(f"\n  [{table_name}] SKIPPED — no absence data (discovery-gated)")
            skipped.add(table_name)
            # Still execute the DDL to create the empty table schema
            try:
                sql_raw = _read_sql(sql_path)
                sql = _render_sql(sql_raw)
                # Only execute CREATE statements, not INSERTs
                for stmt in sql.split(";"):
                    stmt = stmt.strip()
                    if stmt and "CREATE" in stmt.upper():
                        execute(stmt)
                print(f"    Schema created (empty table)")
            except Exception as e:
                print(f"    Warning: could not create schema — {e}")
            continue

        # Check dependencies
        unmet = [d for d in deps if d not in completed and d not in skipped]
        if any(d in failed for d in deps):
            print(f"\n  [{table_name}] SKIPPED — dependency failed: {[d for d in deps if d in failed]}")
            skipped.add(table_name)
            continue

        print(f"\n  [{table_name}] Refreshing...")
        start = time.time()
        log_id = _log_start(table_name, mode)

        try:
            status, row_count, error = _execute_sql_file(
                table_name, sql_path, mode, date_filter
            )
            duration_ms = int((time.time() - start) * 1000)
            _log_finish(log_id, row_count, status, error, duration_ms)
            completed.add(table_name)
            print(f"    OK — {row_count:,} rows ({duration_ms:,}ms)")

        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            error_msg = str(e)
            _log_finish(log_id, 0, "error", error_msg, duration_ms)
            failed.add(table_name)
            print(f"    FAILED — {error_msg[:200]}")

    total_duration = int((time.time() - total_start) * 1000)

    print("\n" + "=" * 60)
    print(f"REFRESH COMPLETE — {total_duration:,}ms")
    print(f"  Completed: {len(completed)}")
    print(f"  Skipped:   {len(skipped)}")
    print(f"  Failed:    {len(failed)}")
    if failed:
        print(f"  Failed tables: {sorted(failed)}")
    print("=" * 60)

    return {
        "mode": mode,
        "completed": sorted(completed),
        "skipped": sorted(skipped),
        "failed": sorted(failed),
        "duration_ms": total_duration,
    }
