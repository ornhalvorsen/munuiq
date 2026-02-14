-- 2.4 Daily Fleet Group Mix
-- Grain: customer_id x order_date x group_set x group_value
-- Derived from 2.3 daily_location_group_mix

CREATE OR REPLACE TABLE {TARGET_SCHEMA}.daily_fleet_group_mix AS
WITH fleet_agg AS (
    SELECT
        customer_id,
        order_date,
        group_set,
        group_value,
        SUM(net_revenue)      AS net_revenue,
        SUM(quantity_sold)    AS quantity_sold,
        COUNT(DISTINCT revenue_unit_id) AS location_count
    FROM {TARGET_SCHEMA}.daily_location_group_mix
    GROUP BY customer_id, order_date, group_set, group_value
)
SELECT
    fa.*,
    100.0 * fa.net_revenue / NULLIF(
        SUM(fa.net_revenue) OVER (
            PARTITION BY fa.customer_id, fa.order_date, fa.group_set
        ), 0
    ) AS revenue_share_pct,
    100.0 * fa.quantity_sold / NULLIF(
        SUM(fa.quantity_sold) OVER (
            PARTITION BY fa.customer_id, fa.order_date, fa.group_set
        ), 0
    ) AS quantity_share_pct
FROM fleet_agg fa;
