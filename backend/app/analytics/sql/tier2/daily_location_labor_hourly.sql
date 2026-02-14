-- 2.9 Daily Location Labor Hourly
-- Grain: customer_id x revenue_unit_id x order_date x hour

CREATE OR REPLACE TABLE {TARGET_SCHEMA}.daily_location_labor_hourly AS
WITH hours_range AS (
    SELECT UNNEST(GENERATE_SERIES(0, 23)) AS hour
),
punchclock_hourly AS (
    -- Prorate punchclock hours into hour buckets
    SELECT
        COALESCE(dm.munu_customer_id) AS customer_id,
        COALESCE(dm.merged_into, dm.munu_revenue_unit_id) AS revenue_unit_id,
        pc.date AS order_date,
        hr.hour,
        pc.employee_id,
        -- Prorated hours: overlap between [clock_in, clock_out] and [hour_start, hour_end]
        GREATEST(0,
            EXTRACT(EPOCH FROM (
                LEAST(pc.clock_out, pc.date::TIMESTAMP + (hr.hour + 1) * INTERVAL '1 HOUR')
                - GREATEST(pc.clock_in, pc.date::TIMESTAMP + hr.hour * INTERVAL '1 HOUR')
            )) / 3600.0
        ) AS hours_in_hour,
        COALESCE(pr.hourly_rate, sal.effective_hourly_rate, 0) AS hourly_rate
    FROM planday.punchclock_shifts pc
    JOIN reference.department_mapping dm
        ON dm.planday_department_id = pc.department_id
        AND dm.planday_portal_name = pc.portal_name
    LEFT JOIN planday.pay_rates pr
        ON pr.employee_id = pc.employee_id
        AND pr.employee_group_id = pc.employee_group_id
        AND pr.portal_name = pc.portal_name
    LEFT JOIN planday.salaries sal
        ON sal.employee_id = pc.employee_id
        AND sal.portal_name = pc.portal_name
    CROSS JOIN hours_range hr
    WHERE dm.mapping_type = 'store'
      AND pc.approved = true
      AND pc.clock_in < pc.date::TIMESTAMP + (hr.hour + 1) * INTERVAL '1 HOUR'
      AND pc.clock_out > pc.date::TIMESTAMP + hr.hour * INTERVAL '1 HOUR'
      {date_filter}
),
hourly_labor AS (
    SELECT
        customer_id,
        revenue_unit_id,
        order_date,
        hour,
        COUNT(DISTINCT employee_id) AS actual_staff,
        SUM(hours_in_hour)          AS actual_hours_in_hour,
        SUM(hours_in_hour * hourly_rate) AS labor_cost_in_hour
    FROM punchclock_hourly
    WHERE hours_in_hour > 0
    GROUP BY customer_id, revenue_unit_id, order_date, hour
),
hourly_transactions AS (
    SELECT
        o.customer_id,
        o.revenue_unit_id,
        o.order_date,
        EXTRACT(HOUR FROM o.order_time) AS hour,
        COUNT(DISTINCT o.soid) AS transactions_in_hour,
        SUM(ol.net_amount)     AS revenue_in_hour
    FROM munu.orders o
    JOIN munu.order_lines ol
        ON o.customer_id = ol.customer_id AND o.soid = ol.soid
    WHERE o.state = 'committed'
      AND ol.net_amount IS NOT NULL
      AND o.revenue_unit_id IS NOT NULL
      AND NOT regexp_matches(ol.article_name, '\d+.*\bfor\s+\d+')
      {date_filter}
    GROUP BY o.customer_id, o.revenue_unit_id, o.order_date, EXTRACT(HOUR FROM o.order_time)
)
SELECT
    COALESCE(hl.customer_id, ht.customer_id)         AS customer_id,
    COALESCE(hl.revenue_unit_id, ht.revenue_unit_id) AS revenue_unit_id,
    COALESCE(hl.order_date, ht.order_date)           AS order_date,
    COALESCE(hl.hour, ht.hour)                       AS hour,
    COALESCE(hl.actual_staff, 0)                     AS actual_staff,
    COALESCE(hl.actual_hours_in_hour, 0)             AS actual_hours_in_hour,
    COALESCE(hl.labor_cost_in_hour, 0)               AS labor_cost_in_hour,
    COALESCE(ht.transactions_in_hour, 0)             AS transactions_in_hour,
    COALESCE(ht.revenue_in_hour, 0)                  AS revenue_in_hour,
    CASE WHEN COALESCE(hl.actual_staff, 0) > 0
        THEN COALESCE(ht.transactions_in_hour, 0)::DECIMAL / hl.actual_staff
        ELSE NULL
    END AS transactions_per_staff,
    CASE WHEN COALESCE(hl.actual_staff, 0) > 0
        THEN COALESCE(ht.revenue_in_hour, 0) / hl.actual_staff
        ELSE NULL
    END AS revenue_per_staff
FROM hourly_labor hl
FULL OUTER JOIN hourly_transactions ht
    ON hl.customer_id = ht.customer_id
    AND hl.revenue_unit_id = ht.revenue_unit_id
    AND hl.order_date = ht.order_date
    AND hl.hour = ht.hour;
