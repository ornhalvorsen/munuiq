-- 3.3 Fleet Benchmarks (expanded)
-- Grain: customer_id x metric_name (snapshot)

CREATE OR REPLACE TABLE {TARGET_SCHEMA}.fleet_benchmarks AS
WITH location_metrics AS (
    SELECT
        customer_id,
        revenue_unit_id,
        t28_avg_daily_revenue   AS daily_revenue,
        t28_avg_daily_orders    AS daily_orders,
        t28_avg_ticket          AS avg_order_value,
        t28_revenue_per_labor_hour AS revenue_per_labor_hour,
        t28_labor_cost_pct      AS labor_cost_pct,
        t28_orders_per_labor_hour AS orders_per_labor_hour
    FROM {TARGET_SCHEMA}.location_trailing_metrics
    WHERE t28_avg_daily_revenue IS NOT NULL
),
unpivoted AS (
    SELECT customer_id, revenue_unit_id, 'daily_revenue' AS metric_name, daily_revenue AS val FROM location_metrics WHERE daily_revenue IS NOT NULL
    UNION ALL
    SELECT customer_id, revenue_unit_id, 'daily_orders', daily_orders FROM location_metrics WHERE daily_orders IS NOT NULL
    UNION ALL
    SELECT customer_id, revenue_unit_id, 'avg_order_value', avg_order_value FROM location_metrics WHERE avg_order_value IS NOT NULL
    UNION ALL
    SELECT customer_id, revenue_unit_id, 'revenue_per_labor_hour', revenue_per_labor_hour FROM location_metrics WHERE revenue_per_labor_hour IS NOT NULL
    UNION ALL
    SELECT customer_id, revenue_unit_id, 'labor_cost_pct', labor_cost_pct FROM location_metrics WHERE labor_cost_pct IS NOT NULL
    UNION ALL
    SELECT customer_id, revenue_unit_id, 'orders_per_labor_hour', orders_per_labor_hour FROM location_metrics WHERE orders_per_labor_hour IS NOT NULL
)
SELECT
    customer_id,
    metric_name,
    COUNT(DISTINCT revenue_unit_id)    AS location_count,
    AVG(val)                           AS fleet_avg,
    MEDIAN(val)                        AS fleet_median,
    QUANTILE_CONT(val, 0.25)           AS fleet_p25,
    QUANTILE_CONT(val, 0.75)           AS fleet_p75,
    MIN(val)                           AS fleet_min,
    MAX(val)                           AS fleet_max
FROM unpivoted
GROUP BY customer_id, metric_name;
