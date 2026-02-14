# DuckDB / MotherDuck Learnings

Lessons learned building the analytics layer on MotherDuck (DuckDB cloud). Reference this when implementing for new restaurant businesses.

---

## Connection & Authentication

### Service Account Tokens
- MotherDuck service account tokens are scoped to a **specific workspace**
- Different service accounts may name the same underlying database differently (`KS2` vs `KS2-Service Agent Read`)
- **Always run `SHOW DATABASES`** after connecting with a new token to discover the actual database name
- R/W tokens have `"readOnly": false, "tokenType": "read_write"` in the JWT payload
- R/O tokens return `"read-only"` errors on `CREATE SCHEMA` — handle gracefully for discovery-only runs

### Cross-Database Queries
- **Cross-database queries between different MotherDuck workspaces DO NOT work**
- `ATTACH` from local DuckDB to MotherDuck requires SSO auth, not token-in-URL
- Solution: analytics schema lives in the **same database** as source tables, using a single R/W token
- Fully-qualified `"Other DB".schema.table` only works within the same workspace/account

### Connection Pattern
```python
conn = duckdb.connect(f"md:?motherduck_token={token}")
conn.execute(f'USE "{database_name}"')  # Quotes needed for names with spaces
conn.execute("CREATE SCHEMA IF NOT EXISTS analytics")
```

---

## SQL Syntax Differences

### Reserved Words
These words are **reserved** in DuckDB and cannot be used as CTE/alias names without quoting:
- `trailing` — use `trail_calcs` or `trailing_data` instead
- `leading`
- `window`
- `order`
- `group`
- `offset`
- `limit`

### No Sequences (MotherDuck)
- `CREATE SEQUENCE` and `nextval()` **do not work** on MotherDuck
- Use `INTEGER PRIMARY KEY` for auto-increment (DuckDB assigns rowid)
- For manual IDs: `(SELECT COALESCE(MAX(id), 0) + 1 FROM table)`

### Interval Arithmetic
- `MAKE_INTERVAL(hours := N)` **does not exist** on MotherDuck
- Use multiplication instead: `N * INTERVAL '1 HOUR'`
- For timestamp + hours: `date_col::TIMESTAMP + hour_int * INTERVAL '1 HOUR'`
- Works: `pc.date::TIMESTAMP + hr.hour * INTERVAL '1 HOUR'`
- Fails: `INTERVAL hr.hour HOUR` (variable in INTERVAL literal not allowed)

### ILIKE ANY
- `column ILIKE ANY(['pat1', 'pat2'])` causes: `Parser Error: Unsupported comparison "~~*" for ANY/ALL subquery`
- Use multiple `OR` conditions instead:
  ```sql
  WHERE st.name ILIKE '%syk%'
     OR st.name ILIKE '%egenmelding%'
     OR st.name ILIKE '%fravær%'
  ```

### regexp_matches
- `regexp_matches(string, pattern)` returns boolean in DuckDB (not match groups like PostgreSQL)
- `NOT regexp_matches(NULL, pattern)` = NULL = row excluded — be careful with NULLable columns
- Consider `COALESCE(NOT regexp_matches(col, pattern), true)` for NULL safety

### STRFTIME
- DuckDB: `STRFTIME(date_col, '%A')` — date first, format second
- This is opposite to some other databases

### GROUP BY with Expressions
- DuckDB requires all non-aggregated SELECT expressions in GROUP BY
- Unlike PostgreSQL, it does NOT infer functional dependencies
- `EXTRACT(DOW FROM date_col)` must appear in GROUP BY if in SELECT

### COALESCE with Single Argument
- `COALESCE(dm.munu_customer_id)` works but is a no-op — DuckDB accepts it silently
- Not harmful but semantically confusing; just use the column directly

---

## Data Model Gotchas (KS2 / Munu)

### Order State Values
- **`committed`** = valid/completed orders (NOT 'completed')
- **`cancelled`** = cancelled orders
- Always verify with `SELECT state, COUNT(*) FROM munu.orders GROUP BY state` on new databases

### Location Joins
- Use `munu.revenue_units` (NOT `munu.installations`)
- `orders.inid` is **ALWAYS empty** — never join on it
- Correct join: `o.customer_id = ru.customer_id AND o.revenue_unit_id = ru.revenue_unit_id`

### Labor Data Join Chain
```
planday.punchclock_shifts
  → reference.department_mapping (planday_department_id + planday_portal_name)
    → munu_customer_id, munu_revenue_unit_id, merged_into
```
- Use `COALESCE(dm.merged_into, dm.munu_revenue_unit_id)` for merged locations
- Filter: `mapping_type = 'store'` (excludes production, admin, etc.)
- Filter: `approved = true` on punchclock_shifts

### Pay Rate Coverage
- `planday.pay_rates` may have **0 rows** matching punchclock employees
- `planday.salaries.effective_hourly_rate` is the fallback
- Coverage may be very low (e.g., 48/782 = 6%) — labor cost calculations will have gaps
- Always LEFT JOIN both and use `COALESCE(pr.hourly_rate, sal.effective_hourly_rate, 0)`

### Bundle SKU Detection
- Bundle regex: `\d+.*\bfor\s+\d+` matches "3 for 100" type product names
- Apply with `NOT regexp_matches(ol.article_name, '\d+.*\bfor\s+\d+')` on order_lines
- Analytics cubes already apply this — do NOT re-filter on analytics tables

### Employee Groups
- `employee_group_id` in `punchclock_shifts` may not always be populated
- JOIN to `employee_groups` for role names (Baker, Butikkleder, etc.)
- Filter out legacy groups: `WHERE eg.name NOT LIKE 'Gammel%'`

---

## MotherDuck Operational Notes

### Transient Failures
- MotherDuck occasionally returns `UNAVAILABLE, RPC 'CATALOG_LOOKUP'` errors
- These are transient — a retry typically succeeds
- Implement retry logic for production pipelines (analytics refresh orchestrator handles this via dependency skipping)

### Performance
- Full refresh of 20 tables with 7.9M source orders takes ~2.5 minutes
- Large tables (2.5M+ rows like daily_location_product) take ~10 seconds each
- Cross join with 24-hour range (hourly cube) on 97K punchclock rows → 421K rows in ~8 seconds

### Schema Management
- `CREATE OR REPLACE TABLE` is the standard pattern for analytics refreshes
- `CREATE TABLE IF NOT EXISTS` for support/config tables that should preserve data
- Always use `{TARGET_SCHEMA}.table_name` template variable for portability

---

## Template Variable Pattern

SQL files use template variables replaced at runtime:
- `{SOURCE_DB}.` — source database prefix (empty string when same-database)
- `{TARGET_SCHEMA}` — analytics schema name (default: `analytics`)
- `{date_filter}` — incremental date range filter (empty for full refresh)

The `_render_sql()` function replaces `{SOURCE_DB}.` as a unit — when `SOURCE_DB=""`, it becomes empty string, so `{SOURCE_DB}.munu.orders` → `munu.orders`.

---

## Checklist for New Implementation

1. Get MotherDuck token → `SHOW DATABASES` → note actual database name
2. Check order state values: `SELECT DISTINCT state FROM munu.orders`
3. Verify revenue_units join works: `SELECT COUNT(*) FROM munu.orders o JOIN munu.revenue_units ru ON ...`
4. Check department_mapping exists and mapping_type values
5. Run discovery: `python -m app.analytics --mode discover`
6. Check pay rate coverage in discovery report
7. Run full refresh: `python -m app.analytics --mode full`
8. Validate: sales cube total ≈ raw order_lines total
9. Validate: labor cube hours ≈ raw punchclock_shifts hours
