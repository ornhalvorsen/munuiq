-- 3.7 Hourly Staffing Benchmarks
-- Grain: customer_id x revenue_unit_id x day_of_week x hour (snapshot)

CREATE OR REPLACE TABLE {TARGET_SCHEMA}.hourly_staffing_benchmarks AS
WITH trailing_8w AS (
    SELECT
        customer_id,
        revenue_unit_id,
        EXTRACT(DOW FROM order_date) AS day_of_week,
        hour,
        AVG(transactions_in_hour)    AS avg_transactions,
        AVG(revenue_in_hour)         AS avg_revenue,
        AVG(actual_staff)            AS avg_staff_present,
        AVG(transactions_per_staff)  AS avg_transactions_per_staff,
        AVG(revenue_per_staff)       AS avg_revenue_per_staff
    FROM {TARGET_SCHEMA}.daily_location_labor_hourly
    WHERE order_date >= CURRENT_DATE - 56  -- 8 weeks
    GROUP BY customer_id, revenue_unit_id, EXTRACT(DOW FROM order_date), hour
),
config AS (
    SELECT param_value AS target_txn_per_staff
    FROM {TARGET_SCHEMA}.config_parameters
    WHERE param_key = 'target_transactions_per_staff'
      AND (valid_to IS NULL OR valid_to >= CURRENT_DATE)
    ORDER BY valid_from DESC
    LIMIT 1
)
SELECT
    t.customer_id,
    t.revenue_unit_id,
    t.day_of_week,
    t.hour,
    ROUND(t.avg_transactions, 1)           AS avg_transactions,
    ROUND(t.avg_revenue, 2)                AS avg_revenue,
    ROUND(t.avg_staff_present, 1)          AS avg_staff_present,
    ROUND(t.avg_transactions_per_staff, 1) AS avg_transactions_per_staff,
    ROUND(t.avg_revenue_per_staff, 2)      AS avg_revenue_per_staff,
    CEIL(t.avg_transactions / NULLIF(c.target_txn_per_staff, 0)) AS recommended_staff,
    CEIL(t.avg_transactions / NULLIF(c.target_txn_per_staff, 0))
        - ROUND(t.avg_staff_present) AS staff_delta
FROM trailing_8w t
CROSS JOIN config c
WHERE t.avg_transactions > 0 OR t.avg_staff_present > 0;
