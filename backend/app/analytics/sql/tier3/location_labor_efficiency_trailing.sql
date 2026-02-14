-- 3.6 Location Labor Efficiency Trailing
-- Grain: customer_id x revenue_unit_id (snapshot)

CREATE OR REPLACE TABLE {TARGET_SCHEMA}.location_labor_efficiency_trailing AS
WITH location_eff AS (
    SELECT
        customer_id,
        revenue_unit_id,

        -- 28-day trailing
        AVG(CASE WHEN order_date >= CURRENT_DATE - 28 THEN revenue_per_labor_hour END) AS t28_revenue_per_labor_hour,
        AVG(CASE WHEN order_date >= CURRENT_DATE - 28 THEN orders_per_labor_hour END)  AS t28_transactions_per_labor_hour,
        AVG(CASE WHEN order_date >= CURRENT_DATE - 28 THEN labor_cost_pct END)         AS t28_labor_cost_pct,
        CASE WHEN SUM(CASE WHEN order_date >= CURRENT_DATE - 28 THEN actual_hours_worked END) > 0
            THEN SUM(CASE WHEN order_date >= CURRENT_DATE - 28 THEN overtime_hours END)
                 / SUM(CASE WHEN order_date >= CURRENT_DATE - 28 THEN actual_hours_worked END) * 100
            ELSE NULL
        END AS t28_overtime_pct,
        AVG(CASE WHEN order_date >= CURRENT_DATE - 28 THEN schedule_adherence_pct END) AS t28_schedule_adherence_pct,

        -- WoW delta for revenue_per_labor_hour
        AVG(CASE WHEN order_date >= CURRENT_DATE - 7 THEN revenue_per_labor_hour END)
        - AVG(CASE WHEN order_date BETWEEN CURRENT_DATE - 14 AND CURRENT_DATE - 8 THEN revenue_per_labor_hour END)
        AS wow_revenue_per_labor_hour_delta,

        -- MoM delta for labor_cost_pct
        AVG(CASE WHEN order_date >= CURRENT_DATE - 28 THEN labor_cost_pct END)
        - AVG(CASE WHEN order_date BETWEEN CURRENT_DATE - 56 AND CURRENT_DATE - 29 THEN labor_cost_pct END)
        AS mom_labor_cost_pct_delta

    FROM {TARGET_SCHEMA}.daily_location_labor
    WHERE order_date >= CURRENT_DATE - 90
    GROUP BY customer_id, revenue_unit_id
),
fleet_avgs AS (
    SELECT
        customer_id,
        AVG(t28_revenue_per_labor_hour) AS fleet_avg_revenue_per_labor_hour,
        AVG(t28_labor_cost_pct)         AS fleet_avg_labor_cost_pct
    FROM location_eff
    GROUP BY customer_id
)
SELECT
    le.*,
    fa.fleet_avg_revenue_per_labor_hour,
    le.t28_revenue_per_labor_hour - fa.fleet_avg_revenue_per_labor_hour AS efficiency_vs_fleet_delta,
    fa.fleet_avg_labor_cost_pct,
    le.t28_labor_cost_pct - fa.fleet_avg_labor_cost_pct AS labor_cost_pct_vs_fleet_delta
FROM location_eff le
LEFT JOIN fleet_avgs fa ON le.customer_id = fa.customer_id;
