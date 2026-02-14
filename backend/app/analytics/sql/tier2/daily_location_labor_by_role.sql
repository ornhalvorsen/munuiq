-- 2.7 Daily Location Labor by Role
-- Grain: customer_id x revenue_unit_id x order_date x role_name

CREATE OR REPLACE TABLE {TARGET_SCHEMA}.daily_location_labor_by_role AS
WITH punchclock_by_role AS (
    SELECT
        COALESCE(dm.munu_customer_id) AS customer_id,
        COALESCE(dm.merged_into, dm.munu_revenue_unit_id) AS revenue_unit_id,
        pc.date AS order_date,
        eg.name AS role_name,
        SUM(pc.hours_worked) AS actual_hours_worked,
        SUM(GREATEST(0, pc.hours_worked - 7.5)) AS overtime_hours,
        COUNT(DISTINCT pc.employee_id) AS headcount_present,
        SUM(
            pc.hours_worked
            * COALESCE(pr.hourly_rate, sal.effective_hourly_rate, 0)
        ) AS labor_cost
    FROM {SOURCE_DB}.planday.punchclock_shifts pc
    JOIN {SOURCE_DB}.reference.department_mapping dm
        ON dm.planday_department_id = pc.department_id
        AND dm.planday_portal_name = pc.portal_name
    JOIN {SOURCE_DB}.planday.employee_groups eg
        ON eg.id = pc.employee_group_id
        AND eg.portal_name = pc.portal_name
    LEFT JOIN {SOURCE_DB}.planday.pay_rates pr
        ON pr.employee_id = pc.employee_id
        AND pr.employee_group_id = pc.employee_group_id
        AND pr.portal_name = pc.portal_name
    LEFT JOIN {SOURCE_DB}.planday.salaries sal
        ON sal.employee_id = pc.employee_id
        AND sal.portal_name = pc.portal_name
    WHERE dm.mapping_type = 'store'
      AND pc.approved = true
      AND eg.name NOT LIKE 'Gammel%'
      {date_filter}
    GROUP BY
        COALESCE(dm.munu_customer_id),
        COALESCE(dm.merged_into, dm.munu_revenue_unit_id),
        pc.date,
        eg.name
),
scheduled_by_role AS (
    SELECT
        COALESCE(dm.munu_customer_id) AS customer_id,
        COALESCE(dm.merged_into, dm.munu_revenue_unit_id) AS revenue_unit_id,
        CAST(s.start_date_time AS DATE) AS order_date,
        eg.name AS role_name,
        SUM(EXTRACT(EPOCH FROM (s.end_date_time - s.start_date_time)) / 3600.0) AS scheduled_hours,
        COUNT(DISTINCT s.employee_id) AS headcount_scheduled
    FROM {SOURCE_DB}.planday.shifts s
    JOIN {SOURCE_DB}.reference.department_mapping dm
        ON dm.planday_department_id = s.department_id
        AND dm.planday_portal_name = s.portal_name
    JOIN {SOURCE_DB}.planday.employee_groups eg
        ON eg.id = s.employee_group_id
        AND eg.portal_name = s.portal_name
    WHERE dm.mapping_type = 'store'
      AND eg.name NOT LIKE 'Gammel%'
      {date_filter}
    GROUP BY
        COALESCE(dm.munu_customer_id),
        COALESCE(dm.merged_into, dm.munu_revenue_unit_id),
        CAST(s.start_date_time AS DATE),
        eg.name
)
SELECT
    COALESCE(pr.customer_id, sr.customer_id)         AS customer_id,
    COALESCE(pr.revenue_unit_id, sr.revenue_unit_id) AS revenue_unit_id,
    COALESCE(pr.order_date, sr.order_date)           AS order_date,
    COALESCE(pr.role_name, sr.role_name)             AS role_name,
    COALESCE(sr.scheduled_hours, 0)                  AS scheduled_hours,
    COALESCE(pr.actual_hours_worked, 0)              AS actual_hours_worked,
    COALESCE(pr.overtime_hours, 0)                   AS overtime_hours,
    COALESCE(sr.headcount_scheduled, 0)              AS headcount_scheduled,
    COALESCE(pr.headcount_present, 0)                AS headcount_present,
    COALESCE(pr.labor_cost, 0)                       AS labor_cost
FROM punchclock_by_role pr
FULL OUTER JOIN scheduled_by_role sr
    ON pr.customer_id = sr.customer_id
    AND pr.revenue_unit_id = sr.revenue_unit_id
    AND pr.order_date = sr.order_date
    AND pr.role_name = sr.role_name;
