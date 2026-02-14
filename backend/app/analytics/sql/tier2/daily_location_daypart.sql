-- 2.5 Daily Location Daypart
-- Grain: customer_id x revenue_unit_id x order_date x daypart_name

CREATE OR REPLACE TABLE {TARGET_SCHEMA}.daily_location_daypart AS
WITH order_daypart AS (
    SELECT
        o.customer_id,
        o.revenue_unit_id,
        o.order_date,
        o.soid,
        ol.net_amount,
        ol.quantity,
        EXTRACT(HOUR FROM o.order_time) AS order_hour,
        CASE
            WHEN EXTRACT(HOUR FROM o.order_time) < 6  THEN 'Morning'
            WHEN EXTRACT(HOUR FROM o.order_time) < 11 THEN 'Morning'
            WHEN EXTRACT(HOUR FROM o.order_time) < 14 THEN 'Lunch'
            WHEN EXTRACT(HOUR FROM o.order_time) < 17 THEN 'Afternoon'
            WHEN EXTRACT(HOUR FROM o.order_time) < 22 THEN 'Evening'
            ELSE 'Evening'
        END AS daypart_name
    FROM {SOURCE_DB}.munu.orders o
    JOIN {SOURCE_DB}.munu.order_lines ol
        ON o.customer_id = ol.customer_id AND o.soid = ol.soid
    WHERE o.state = 'committed'
      AND ol.net_amount IS NOT NULL
      AND o.revenue_unit_id IS NOT NULL
      AND NOT regexp_matches(ol.article_name, '\d+.*\bfor\s+\d+')
      {date_filter}
),
daypart_agg AS (
    SELECT
        customer_id,
        revenue_unit_id,
        order_date,
        daypart_name,
        SUM(net_amount)          AS net_revenue,
        COUNT(DISTINCT soid)     AS order_count,
        SUM(quantity)            AS item_quantity,
        SUM(net_amount) / NULLIF(COUNT(DISTINCT soid), 0) AS avg_order_value
    FROM order_daypart
    GROUP BY customer_id, revenue_unit_id, order_date, daypart_name
)
SELECT
    da.*,
    100.0 * da.net_revenue / NULLIF(
        SUM(da.net_revenue) OVER (PARTITION BY da.customer_id, da.revenue_unit_id, da.order_date), 0
    ) AS revenue_share_pct,
    100.0 * da.order_count / NULLIF(
        SUM(da.order_count) OVER (PARTITION BY da.customer_id, da.revenue_unit_id, da.order_date), 0
    ) AS order_share_pct
FROM daypart_agg da;
