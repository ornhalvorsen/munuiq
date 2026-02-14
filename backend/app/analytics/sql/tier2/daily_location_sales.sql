-- 2.1 Daily Location Sales
-- Grain: customer_id x revenue_unit_id x order_date

CREATE OR REPLACE TABLE {TARGET_SCHEMA}.daily_location_sales AS
SELECT
    o.customer_id,
    o.revenue_unit_id,
    o.order_date,
    ru.name AS location_name,
    SUM(ol.net_amount)                          AS net_revenue,
    SUM(ol.gross_amount)                        AS gross_revenue,
    SUM(ol.vat_amount)                          AS vat_amount,
    SUM(ol.discount_amount)                     AS discount_amount,
    COUNT(DISTINCT o.soid)                      AS order_count,
    SUM(ol.quantity)                             AS item_quantity,
    SUM(ol.net_amount) / NULLIF(COUNT(DISTINCT o.soid), 0) AS avg_order_value,
    EXTRACT(DOW FROM o.order_date)              AS day_of_week,
    STRFTIME(o.order_date, '%A')                AS day_name,
    EXTRACT(WEEK FROM o.order_date)             AS week_number,
    EXTRACT(MONTH FROM o.order_date)            AS month_number,
    EXTRACT(YEAR FROM o.order_date)             AS year_number
FROM {SOURCE_DB}.munu.orders o
JOIN {SOURCE_DB}.munu.order_lines ol
    ON o.customer_id = ol.customer_id AND o.soid = ol.soid
JOIN {SOURCE_DB}.munu.revenue_units ru
    ON o.customer_id = ru.customer_id AND o.revenue_unit_id = ru.revenue_unit_id
WHERE o.state = 'committed'
  AND ol.net_amount IS NOT NULL
  AND o.revenue_unit_id IS NOT NULL
  AND NOT regexp_matches(ol.article_name, '\d+.*\bfor\s+\d+')
  {date_filter}
GROUP BY
    o.customer_id,
    o.revenue_unit_id,
    o.order_date,
    ru.name,
    EXTRACT(DOW FROM o.order_date),
    STRFTIME(o.order_date, '%A'),
    EXTRACT(WEEK FROM o.order_date),
    EXTRACT(MONTH FROM o.order_date),
    EXTRACT(YEAR FROM o.order_date);
