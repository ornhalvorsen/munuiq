-- 2.2 Daily Location Product
-- Grain: customer_id x revenue_unit_id x order_date x article_id

CREATE OR REPLACE TABLE {TARGET_SCHEMA}.daily_location_product AS
SELECT
    o.customer_id,
    o.revenue_unit_id,
    o.order_date,
    ol.article_id,
    ol.article_name,
    au.category,
    au.subcategory,
    SUM(ol.net_amount)                                      AS net_revenue,
    SUM(ol.quantity)                                         AS quantity_sold,
    SUM(ol.net_amount) / NULLIF(SUM(ol.quantity), 0)        AS avg_unit_price
FROM {SOURCE_DB}.munu.orders o
JOIN {SOURCE_DB}.munu.order_lines ol
    ON o.customer_id = ol.customer_id AND o.soid = ol.soid
LEFT JOIN {SOURCE_DB}.munu.articles_unified au
    ON ol.customer_id = au.customer_id AND ol.article_id = au.article_id
WHERE o.state = 'committed'
  AND ol.net_amount IS NOT NULL
  AND o.revenue_unit_id IS NOT NULL
  AND NOT regexp_matches(ol.article_name, '\d+.*\bfor\s+\d+')
  AND (au.category_is_active = true OR au.category_is_active IS NULL)
  {date_filter}
GROUP BY
    o.customer_id,
    o.revenue_unit_id,
    o.order_date,
    ol.article_id,
    ol.article_name,
    au.category,
    au.subcategory;
