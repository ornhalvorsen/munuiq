"""
Create the denormalized sales_fact view in the munuiq database.

Joins orders + order_lines + revenue_units + articles + onboarding category mappings
into a single flat view so the LLM can query sales data without multi-table JOINs.
"""

from app import management_db

_SALES_FACT_DDL = """
CREATE OR REPLACE VIEW sales_fact AS
SELECT
    ol.customer_id,
    o.order_date,
    o.soid,
    ru.name                                                    AS location_name,
    ru.revenue_unit_id,
    ol.article_name                                            AS product_name,
    a.article_group_name                                       AS raw_category,
    COALESCE(cat_map.unified_category, a.article_group_name)   AS category,
    ol.quantity,
    ol.net_amount,
    ol.gross_amount,
    o.total_amount                                             AS order_total
FROM "KS2-Service Agent Read".munu.order_lines ol
JOIN "KS2-Service Agent Read".munu.orders o
    ON ol.customer_id = o.customer_id AND ol.soid = o.soid
JOIN "KS2-Service Agent Read".munu.revenue_units ru
    ON o.customer_id = ru.customer_id AND o.revenue_unit_id = ru.revenue_unit_id
LEFT JOIN "KS2-Service Agent Read".munu.articles a
    ON ol.article_id = a.article_id AND ol.customer_id = a.customer_id
LEFT JOIN (
    SELECT customer_id, source_key,
        FIRST(COALESCE(final_value, proposed_value)) AS unified_category
    FROM onboarding_mappings
    WHERE mapping_type = 'category' AND status = 'approved'
    GROUP BY customer_id, source_key
) cat_map
    ON cat_map.customer_id = ol.customer_id
    AND cat_map.source_key = CONCAT(
        COALESCE(a.article_group_name, ''), '|', COALESCE(a.article_subgroup_name, '')
    )
"""


def create_sales_view() -> bool:
    """Create or replace the sales_fact view via management_db connection.

    Returns True on success, False if management_db is unavailable.
    """
    conn = management_db._conn
    if conn is None:
        print("Sales view: management_db not connected — skipping.")
        return False
    try:
        with management_db._lock:
            conn.execute(_SALES_FACT_DDL)
        print("Sales fact view created in munuiq database.")
        return True
    except Exception as e:
        print(f"Sales view: failed to create — {e}")
        return False
