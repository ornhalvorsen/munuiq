-- 3.2 Location Group Mix Trailing
-- Grain: customer_id x revenue_unit_id x group_set x group_value (snapshot)

CREATE OR REPLACE TABLE {TARGET_SCHEMA}.location_group_mix_trailing AS
WITH location_mix AS (
    SELECT
        customer_id,
        revenue_unit_id,
        group_set,
        group_value,
        AVG(CASE WHEN order_date >= CURRENT_DATE - 28 THEN revenue_share_pct END) AS t28_avg_revenue_share,
        AVG(CASE WHEN order_date >= CURRENT_DATE - 28 THEN quantity_share_pct END) AS t28_avg_quantity_share,
        SUM(CASE WHEN order_date >= CURRENT_DATE - 28 THEN net_revenue END) AS t28_total_revenue
    FROM {TARGET_SCHEMA}.daily_location_group_mix
    WHERE order_date >= CURRENT_DATE - 28
    GROUP BY customer_id, revenue_unit_id, group_set, group_value
),
fleet_mix AS (
    SELECT
        customer_id,
        group_set,
        group_value,
        AVG(revenue_share_pct) AS fleet_avg_revenue_share,
        AVG(quantity_share_pct) AS fleet_avg_quantity_share
    FROM {TARGET_SCHEMA}.daily_fleet_group_mix
    WHERE order_date >= CURRENT_DATE - 28
    GROUP BY customer_id, group_set, group_value
)
SELECT
    lm.customer_id,
    lm.revenue_unit_id,
    lm.group_set,
    lm.group_value,
    lm.t28_avg_revenue_share,
    lm.t28_avg_quantity_share,
    lm.t28_total_revenue,
    fm.fleet_avg_revenue_share,
    fm.fleet_avg_quantity_share,
    lm.t28_avg_revenue_share - fm.fleet_avg_revenue_share AS share_vs_fleet_delta
FROM location_mix lm
LEFT JOIN fleet_mix fm
    ON lm.customer_id = fm.customer_id
    AND lm.group_set = fm.group_set
    AND lm.group_value = fm.group_value;
