-- 2.6 Daily Location Labor (expanded)
-- Grain: customer_id x revenue_unit_id x order_date
-- Depends on: 2.1 daily_location_sales

CREATE OR REPLACE TABLE {TARGET_SCHEMA}.daily_location_labor AS
WITH punchclock_labor AS (
    -- Actual hours worked from punchclock
    SELECT
        COALESCE(dm.munu_customer_id) AS customer_id,
        COALESCE(dm.merged_into, dm.munu_revenue_unit_id) AS revenue_unit_id,
        pc.date AS order_date,
        SUM(pc.hours_worked) AS actual_hours_worked,
        SUM(GREATEST(0, pc.hours_worked - 7.5)) AS overtime_hours,
        COUNT(DISTINCT pc.employee_id) AS headcount_present,
        -- Base cost: min(hours, 7.5) * rate
        SUM(
            LEAST(pc.hours_worked, 7.5)
            * COALESCE(pr.hourly_rate, sal.effective_hourly_rate, 0)
        ) AS base_labor_cost,
        -- Overtime cost: max(0, hours-7.5) * rate * 1.5
        SUM(
            GREATEST(0, pc.hours_worked - 7.5)
            * COALESCE(pr.hourly_rate, sal.effective_hourly_rate, 0)
            * 1.5
        ) AS overtime_cost
    FROM {SOURCE_DB}.planday.punchclock_shifts pc
    JOIN {SOURCE_DB}.reference.department_mapping dm
        ON dm.planday_department_id = pc.department_id
        AND dm.planday_portal_name = pc.portal_name
    LEFT JOIN {SOURCE_DB}.planday.pay_rates pr
        ON pr.employee_id = pc.employee_id
        AND pr.employee_group_id = pc.employee_group_id
        AND pr.portal_name = pc.portal_name
    LEFT JOIN {SOURCE_DB}.planday.salaries sal
        ON sal.employee_id = pc.employee_id
        AND sal.portal_name = pc.portal_name
    WHERE dm.mapping_type = 'store'
      AND pc.approved = true
      {date_filter}
    GROUP BY
        COALESCE(dm.munu_customer_id),
        COALESCE(dm.merged_into, dm.munu_revenue_unit_id),
        pc.date
),
scheduled_labor AS (
    -- Scheduled hours from shifts
    SELECT
        COALESCE(dm.munu_customer_id) AS customer_id,
        COALESCE(dm.merged_into, dm.munu_revenue_unit_id) AS revenue_unit_id,
        CAST(s.start_date_time AS DATE) AS order_date,
        SUM(EXTRACT(EPOCH FROM (s.end_date_time - s.start_date_time)) / 3600.0) AS scheduled_hours,
        COUNT(DISTINCT s.employee_id) AS headcount_scheduled
    FROM {SOURCE_DB}.planday.shifts s
    JOIN {SOURCE_DB}.reference.department_mapping dm
        ON dm.planday_department_id = s.department_id
        AND dm.planday_portal_name = s.portal_name
    WHERE dm.mapping_type = 'store'
      {date_filter}
    GROUP BY
        COALESCE(dm.munu_customer_id),
        COALESCE(dm.merged_into, dm.munu_revenue_unit_id),
        CAST(s.start_date_time AS DATE)
)
SELECT
    COALESCE(pl.customer_id, sl.customer_id) AS customer_id,
    COALESCE(pl.revenue_unit_id, sl.revenue_unit_id) AS revenue_unit_id,
    COALESCE(pl.order_date, sl.order_date) AS order_date,
    COALESCE(sl.scheduled_hours, 0)         AS scheduled_hours,
    COALESCE(pl.actual_hours_worked, 0)     AS actual_hours_worked,
    COALESCE(pl.overtime_hours, 0)          AS overtime_hours,
    COALESCE(sl.headcount_scheduled, 0)     AS headcount_scheduled,
    COALESCE(pl.headcount_present, 0)       AS headcount_present,
    COALESCE(pl.base_labor_cost, 0)         AS base_labor_cost,
    COALESCE(pl.overtime_cost, 0)           AS overtime_cost,
    COALESCE(pl.base_labor_cost, 0) + COALESCE(pl.overtime_cost, 0) AS total_labor_cost,
    -- Join sales metrics
    COALESCE(ds.net_revenue, 0)             AS net_revenue,
    COALESCE(ds.order_count, 0)             AS order_count,
    -- Derived metrics
    CASE WHEN COALESCE(ds.net_revenue, 0) > 0
        THEN (COALESCE(pl.base_labor_cost, 0) + COALESCE(pl.overtime_cost, 0))
             / ds.net_revenue * 100
        ELSE NULL
    END AS labor_cost_pct,
    CASE WHEN COALESCE(pl.actual_hours_worked, 0) > 0
        THEN COALESCE(ds.net_revenue, 0) / pl.actual_hours_worked
        ELSE NULL
    END AS revenue_per_labor_hour,
    CASE WHEN COALESCE(pl.actual_hours_worked, 0) > 0
        THEN COALESCE(ds.order_count, 0)::DECIMAL / pl.actual_hours_worked
        ELSE NULL
    END AS orders_per_labor_hour,
    CASE WHEN COALESCE(sl.scheduled_hours, 0) > 0
        THEN COALESCE(pl.actual_hours_worked, 0) / sl.scheduled_hours * 100
        ELSE NULL
    END AS schedule_adherence_pct
FROM punchclock_labor pl
FULL OUTER JOIN scheduled_labor sl
    ON pl.customer_id = sl.customer_id
    AND pl.revenue_unit_id = sl.revenue_unit_id
    AND pl.order_date = sl.order_date
LEFT JOIN {TARGET_SCHEMA}.daily_location_sales ds
    ON ds.customer_id = COALESCE(pl.customer_id, sl.customer_id)
    AND ds.revenue_unit_id = COALESCE(pl.revenue_unit_id, sl.revenue_unit_id)
    AND ds.order_date = COALESCE(pl.order_date, sl.order_date);
