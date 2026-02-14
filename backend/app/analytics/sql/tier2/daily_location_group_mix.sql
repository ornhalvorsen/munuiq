-- 2.3 Daily Location Group Mix
-- Grain: customer_id x revenue_unit_id x order_date x group_set x group_value

CREATE OR REPLACE TABLE {TARGET_SCHEMA}.daily_location_group_mix AS
WITH product_sales AS (
    SELECT
        dp.customer_id,
        dp.revenue_unit_id,
        dp.order_date,
        pg.group_set,
        pg.group_value,
        SUM(dp.net_revenue)    AS net_revenue,
        SUM(dp.quantity_sold)  AS quantity_sold
    FROM {TARGET_SCHEMA}.daily_location_product dp
    JOIN {TARGET_SCHEMA}.product_group_definitions pg
        ON dp.customer_id = pg.customer_id AND dp.article_id = pg.article_id
    GROUP BY
        dp.customer_id,
        dp.revenue_unit_id,
        dp.order_date,
        pg.group_set,
        pg.group_value
)
SELECT
    ps.*,
    100.0 * ps.net_revenue / NULLIF(
        SUM(ps.net_revenue) OVER (
            PARTITION BY ps.customer_id, ps.revenue_unit_id, ps.order_date, ps.group_set
        ), 0
    ) AS revenue_share_pct,
    100.0 * ps.quantity_sold / NULLIF(
        SUM(ps.quantity_sold) OVER (
            PARTITION BY ps.customer_id, ps.revenue_unit_id, ps.order_date, ps.group_set
        ), 0
    ) AS quantity_share_pct
FROM product_sales ps;
