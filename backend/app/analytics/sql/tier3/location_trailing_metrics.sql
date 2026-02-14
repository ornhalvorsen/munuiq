-- 3.1 Location Trailing Metrics (expanded)
-- Grain: customer_id x revenue_unit_id (snapshot)

CREATE OR REPLACE TABLE {TARGET_SCHEMA}.location_trailing_metrics AS
WITH daily AS (
    SELECT
        ds.customer_id,
        ds.revenue_unit_id,
        ds.location_name,
        ds.order_date,
        ds.net_revenue,
        ds.order_count,
        ds.avg_order_value,
        ds.item_quantity / NULLIF(ds.order_count, 0) AS items_per_transaction,
        dl.total_labor_cost,
        dl.labor_cost_pct,
        dl.revenue_per_labor_hour,
        dl.orders_per_labor_hour
    FROM {TARGET_SCHEMA}.daily_location_sales ds
    LEFT JOIN {TARGET_SCHEMA}.daily_location_labor dl
        ON ds.customer_id = dl.customer_id
        AND ds.revenue_unit_id = dl.revenue_unit_id
        AND ds.order_date = dl.order_date
),
trail_calcs AS (
    SELECT
        customer_id,
        revenue_unit_id,
        MAX(location_name) AS location_name,

        -- 7-day trailing
        AVG(CASE WHEN order_date >= CURRENT_DATE - 7 THEN net_revenue END)              AS t7_avg_daily_revenue,
        AVG(CASE WHEN order_date >= CURRENT_DATE - 7 THEN order_count END)              AS t7_avg_daily_orders,
        AVG(CASE WHEN order_date >= CURRENT_DATE - 7 THEN avg_order_value END)          AS t7_avg_ticket,
        AVG(CASE WHEN order_date >= CURRENT_DATE - 7 THEN items_per_transaction END)    AS t7_items_per_txn,
        AVG(CASE WHEN order_date >= CURRENT_DATE - 7 THEN total_labor_cost END)         AS t7_avg_labor_cost,
        AVG(CASE WHEN order_date >= CURRENT_DATE - 7 THEN labor_cost_pct END)           AS t7_labor_cost_pct,
        AVG(CASE WHEN order_date >= CURRENT_DATE - 7 THEN revenue_per_labor_hour END)   AS t7_revenue_per_labor_hour,

        -- 28-day trailing
        AVG(CASE WHEN order_date >= CURRENT_DATE - 28 THEN net_revenue END)             AS t28_avg_daily_revenue,
        AVG(CASE WHEN order_date >= CURRENT_DATE - 28 THEN order_count END)             AS t28_avg_daily_orders,
        AVG(CASE WHEN order_date >= CURRENT_DATE - 28 THEN avg_order_value END)         AS t28_avg_ticket,
        AVG(CASE WHEN order_date >= CURRENT_DATE - 28 THEN items_per_transaction END)   AS t28_items_per_txn,
        AVG(CASE WHEN order_date >= CURRENT_DATE - 28 THEN total_labor_cost END)        AS t28_avg_labor_cost,
        AVG(CASE WHEN order_date >= CURRENT_DATE - 28 THEN labor_cost_pct END)          AS t28_labor_cost_pct,
        AVG(CASE WHEN order_date >= CURRENT_DATE - 28 THEN revenue_per_labor_hour END)  AS t28_revenue_per_labor_hour,
        AVG(CASE WHEN order_date >= CURRENT_DATE - 28 THEN orders_per_labor_hour END)   AS t28_orders_per_labor_hour,

        -- 90-day trailing
        AVG(CASE WHEN order_date >= CURRENT_DATE - 90 THEN net_revenue END)             AS t90_avg_daily_revenue,
        AVG(CASE WHEN order_date >= CURRENT_DATE - 90 THEN order_count END)             AS t90_avg_daily_orders,
        AVG(CASE WHEN order_date >= CURRENT_DATE - 90 THEN avg_order_value END)         AS t90_avg_ticket,
        AVG(CASE WHEN order_date >= CURRENT_DATE - 90 THEN labor_cost_pct END)          AS t90_labor_cost_pct,

        -- WoW deltas (last 7d avg vs previous 7d avg)
        AVG(CASE WHEN order_date >= CURRENT_DATE - 7 THEN net_revenue END)
        - AVG(CASE WHEN order_date BETWEEN CURRENT_DATE - 14 AND CURRENT_DATE - 8 THEN net_revenue END) AS wow_revenue_delta,
        AVG(CASE WHEN order_date >= CURRENT_DATE - 7 THEN order_count END)
        - AVG(CASE WHEN order_date BETWEEN CURRENT_DATE - 14 AND CURRENT_DATE - 8 THEN order_count END) AS wow_orders_delta,

        -- MoM deltas (last 28d avg vs previous 28d avg)
        AVG(CASE WHEN order_date >= CURRENT_DATE - 28 THEN net_revenue END)
        - AVG(CASE WHEN order_date BETWEEN CURRENT_DATE - 56 AND CURRENT_DATE - 29 THEN net_revenue END) AS mom_revenue_delta

    FROM daily
    WHERE order_date >= CURRENT_DATE - 90
    GROUP BY customer_id, revenue_unit_id
)
SELECT
    t.*,
    PERCENT_RANK() OVER (PARTITION BY t.customer_id ORDER BY t.t28_avg_daily_revenue)
        AS revenue_percentile_28d
FROM trail_calcs t;
