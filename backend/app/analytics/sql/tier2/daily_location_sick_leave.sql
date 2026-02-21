-- 2.8 Daily Location Sick Leave (discovery-gated)
-- Grain: customer_id x revenue_unit_id x order_date x absence_category
-- Depends on: absence_type_mapping, daily_location_labor
--
-- Source: planday.shifts → absence_type_mapping → department_mapping → revenue_units
-- Absence hours from shift duration, costs from pay rates / salaries.
-- sick_rate_pct = absence_hours / scheduled_hours from daily_location_labor.

CREATE OR REPLACE TABLE {TARGET_SCHEMA}.daily_location_sick_leave AS
WITH absence_shifts AS (
    SELECT
        COALESCE(dm.munu_customer_id) AS customer_id,
        COALESCE(dm.merged_into, dm.munu_revenue_unit_id) AS revenue_unit_id,
        CAST(s.start_date_time AS DATE) AS order_date,
        atm.absence_category,
        atm.cost_bearer,
        s.employee_id,
        -- Shift duration in hours
        EXTRACT(EPOCH FROM (s.end_date_time - s.start_date_time)) / 3600.0 AS shift_hours,
        -- Hourly rate: prefer pay_rates, fallback to salary
        COALESCE(pr.hourly_rate, sal.effective_hourly_rate, 0) AS hourly_rate
    FROM {SOURCE_DB}.planday.shifts s
    JOIN {TARGET_SCHEMA}.absence_type_mapping atm
        ON atm.shift_type_id = s.shift_type_id
        AND atm.portal_name = s.portal_name
    JOIN {SOURCE_DB}.reference.department_mapping dm
        ON dm.planday_department_id = s.department_id
        AND dm.planday_portal_name = s.portal_name
    LEFT JOIN {SOURCE_DB}.planday.pay_rates pr
        ON pr.employee_id = s.employee_id
        AND pr.employee_group_id = s.employee_group_id
        AND pr.portal_name = s.portal_name
    LEFT JOIN {SOURCE_DB}.planday.salaries sal
        ON sal.employee_id = s.employee_id
        AND sal.portal_name = s.portal_name
    WHERE dm.mapping_type = 'store'
      AND dm.munu_revenue_unit_id IS NOT NULL
      -- Exclude vacation from sick leave cube
      AND atm.absence_category != 'vacation'
),
-- 6G cap: NAV hourly max = (6 * grunnbelop) / standard_work_hours_year
nav_cap AS (
    SELECT
        6.0 * cp_g.param_value / cp_h.param_value AS max_nav_hourly_rate
    FROM {TARGET_SCHEMA}.config_parameters cp_g
    CROSS JOIN {TARGET_SCHEMA}.config_parameters cp_h
    WHERE cp_g.param_key = 'grunnbelop'
      AND cp_g.valid_to IS NULL
      AND cp_h.param_key = 'standard_work_hours_year'
      AND cp_h.valid_to IS NULL
),
daily_agg AS (
    SELECT
        a.customer_id,
        a.revenue_unit_id,
        a.order_date,
        a.absence_category,
        SUM(a.shift_hours) AS absence_hours,
        COUNT(*) AS absence_shifts,
        COUNT(DISTINCT a.employee_id) AS employees_absent,
        -- Gross salary cost (full hourly rate * hours)
        SUM(a.shift_hours * a.hourly_rate) AS gross_salary_cost,
        -- Employer-borne cost: employer-paid shifts at full rate
        SUM(CASE WHEN a.cost_bearer = 'employer'
            THEN a.shift_hours * a.hourly_rate
            ELSE 0 END) AS employer_borne_cost,
        -- NAV-borne cost: NAV shifts capped at 6G hourly equivalent
        SUM(CASE WHEN a.cost_bearer = 'nav'
            THEN a.shift_hours * LEAST(a.hourly_rate, nc.max_nav_hourly_rate)
            ELSE 0 END) AS nav_borne_cost
    FROM absence_shifts a
    CROSS JOIN nav_cap nc
    GROUP BY
        a.customer_id,
        a.revenue_unit_id,
        a.order_date,
        a.absence_category
)
SELECT
    da.customer_id,
    da.revenue_unit_id,
    ru.name AS location_name,
    da.order_date,
    da.absence_category,
    ROUND(da.absence_hours, 2) AS absence_hours,
    da.absence_shifts,
    da.employees_absent,
    ROUND(da.gross_salary_cost, 2) AS gross_salary_cost,
    ROUND(da.employer_borne_cost, 2) AS employer_borne_cost,
    ROUND(da.nav_borne_cost, 2) AS nav_borne_cost,
    -- Scheduled hours from labor cube for rate calculation
    COALESCE(dl.scheduled_hours, 0) AS scheduled_hours,
    -- Sick rate: absence hours / scheduled hours * 100
    CASE WHEN COALESCE(dl.scheduled_hours, 0) > 0
        THEN ROUND(da.absence_hours / dl.scheduled_hours * 100, 2)
        ELSE NULL
    END AS sick_rate_pct
FROM daily_agg da
JOIN {SOURCE_DB}.munu.revenue_units ru
    ON ru.customer_id = da.customer_id
    AND ru.revenue_unit_id = da.revenue_unit_id
LEFT JOIN {TARGET_SCHEMA}.daily_location_labor dl
    ON dl.customer_id = da.customer_id
    AND dl.revenue_unit_id = da.revenue_unit_id
    AND dl.order_date = da.order_date;
