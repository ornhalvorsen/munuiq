-- 3.4 Daypart Benchmarks
-- Grain: customer_id x daypart_name x metric_name (snapshot)

CREATE OR REPLACE TABLE {TARGET_SCHEMA}.daypart_benchmarks AS
WITH location_daypart AS (
    SELECT
        customer_id,
        revenue_unit_id,
        daypart_name,
        AVG(net_revenue) AS avg_revenue,
        AVG(order_count) AS avg_orders,
        AVG(revenue_share_pct) AS avg_revenue_share
    FROM {TARGET_SCHEMA}.daily_location_daypart
    WHERE order_date >= CURRENT_DATE - 28
    GROUP BY customer_id, revenue_unit_id, daypart_name
),
unpivoted AS (
    SELECT customer_id, revenue_unit_id, daypart_name, 'avg_revenue' AS metric_name, avg_revenue AS val FROM location_daypart
    UNION ALL
    SELECT customer_id, revenue_unit_id, daypart_name, 'avg_orders', avg_orders FROM location_daypart
    UNION ALL
    SELECT customer_id, revenue_unit_id, daypart_name, 'revenue_share_pct', avg_revenue_share FROM location_daypart
)
SELECT
    customer_id,
    daypart_name,
    metric_name,
    COUNT(DISTINCT revenue_unit_id) AS location_count,
    AVG(val)                        AS fleet_avg,
    MEDIAN(val)                     AS fleet_median,
    QUANTILE_CONT(val, 0.25)        AS fleet_p25,
    QUANTILE_CONT(val, 0.75)        AS fleet_p75,
    MIN(val)                        AS fleet_min,
    MAX(val)                        AS fleet_max
FROM unpivoted
GROUP BY customer_id, daypart_name, metric_name;
