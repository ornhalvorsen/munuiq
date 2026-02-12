"""
Tenant-scoped query enforcement.

Two-layer approach:
  Layer 1 (soft): LLM system prompt includes customer_id constraint
  Layer 2 (hard): Post-process SQL to verify/inject customer_id IN (...) clauses
"""

import re


# Tables that require customer_id filtering (schema.table patterns)
_CUSTOMER_SCOPED_TABLES = {
    "munu.", "admin.", "cakeiteasy.", "planday.", "reference.", "munuiq.",
}


def build_customer_constraint(customer_ids: list[int]) -> str:
    """Build the LLM prompt constraint for customer_id filtering."""
    if not customer_ids:
        return ""
    ids_str = ", ".join(str(c) for c in customer_ids)
    return (
        f"\n\nCRITICAL: Every query MUST include WHERE customer_id IN ({ids_str}) "
        f"on ALL tables from munu, munuiq, admin, cakeiteasy, planday, and reference schemas. "
        f"This is mandatory and must not be omitted."
    )


def inject_customer_filter(sql: str, customer_ids: list[int]) -> str:
    """
    Hard enforcement: verify that customer_id IN (...) exists in the SQL
    for any query touching customer-scoped tables. If missing, inject it.

    This is a safety net — the LLM should already include the filter,
    but this ensures data isolation even if the LLM forgets.
    """
    if not customer_ids:
        return sql  # superadmin or no filter needed

    ids_str = ", ".join(str(c) for c in customer_ids)
    filter_clause = f"customer_id IN ({ids_str})"

    # Check if query touches any customer-scoped tables
    sql_lower = sql.lower()
    touches_scoped = any(prefix in sql_lower for prefix in _CUSTOMER_SCOPED_TABLES)

    if not touches_scoped:
        return sql  # query doesn't touch scoped tables

    # Check if filter already present
    if filter_clause.lower() in sql_lower:
        return sql

    # Also accept single customer_id = N
    if len(customer_ids) == 1:
        single_filter = f"customer_id = {customer_ids[0]}"
        if single_filter.lower() in sql_lower:
            return sql

    # Need to inject the filter
    # Strategy: find WHERE clause and add AND, or add WHERE before ORDER BY/GROUP BY/LIMIT/;
    where_match = re.search(r'\bWHERE\b', sql, re.IGNORECASE)
    if where_match:
        # Insert after WHERE
        pos = where_match.end()
        return sql[:pos] + f" {filter_clause} AND" + sql[pos:]
    else:
        # No WHERE clause — inject before ORDER BY, GROUP BY, HAVING, LIMIT, or end
        for keyword in [r'\bORDER\s+BY\b', r'\bGROUP\s+BY\b', r'\bHAVING\b', r'\bLIMIT\b']:
            m = re.search(keyword, sql, re.IGNORECASE)
            if m:
                pos = m.start()
                return sql[:pos] + f" WHERE {filter_clause} " + sql[pos:]
        # No trailing clause — append
        return sql.rstrip().rstrip(";") + f" WHERE {filter_clause}"
