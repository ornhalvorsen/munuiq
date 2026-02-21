-- 3.5 Location Sick Leave Trailing (discovery-gated)
-- Grain: customer_id x revenue_unit_id (snapshot)
-- Depends on: daily_location_sick_leave, daily_location_labor
--
-- Rolling sick leave metrics per location: 28d/90d/365d rates,
-- cost breakdown, fleet comparison.

CREATE OR REPLACE TABLE {TARGET_SCHEMA}.location_sick_leave_trailing AS
WITH date_bounds AS (
    SELECT
        MAX(order_date) AS latest_date
    FROM {TARGET_SCHEMA}.daily_location_sick_leave
),
-- Aggregate absence hours per location per date (across all categories)
daily_totals AS (
    SELECT
        sl.customer_id,
        sl.revenue_unit_id,
        sl.location_name,
        sl.order_date,
        SUM(sl.absence_hours)       AS absence_hours,
        SUM(sl.absence_shifts)      AS absence_shifts,
        SUM(sl.gross_salary_cost)   AS gross_salary_cost,
        SUM(sl.employer_borne_cost) AS employer_borne_cost,
        SUM(sl.nav_borne_cost)      AS nav_borne_cost,
        -- Category-specific hours for rate breakdown
        SUM(CASE WHEN sl.absence_category = 'egenmelding' THEN sl.absence_hours ELSE 0 END) AS egenmelding_hours,
        SUM(CASE WHEN sl.absence_category = 'sykemelding' THEN sl.absence_hours ELSE 0 END) AS sykemelding_hours,
        SUM(CASE WHEN sl.absence_category = 'egenmelding' THEN sl.absence_shifts ELSE 0 END) AS egenmelding_shifts,
        -- Use max of scheduled_hours (same across categories for same day/location)
        MAX(sl.scheduled_hours) AS scheduled_hours
    FROM {TARGET_SCHEMA}.daily_location_sick_leave sl
    GROUP BY sl.customer_id, sl.revenue_unit_id, sl.location_name, sl.order_date
),
-- Get scheduled hours for days with NO absence (needed for rate denominator)
labor_with_absence AS (
    SELECT
        dl.customer_id,
        dl.revenue_unit_id,
        dl.order_date,
        dl.scheduled_hours,
        COALESCE(dt.absence_hours, 0) AS absence_hours,
        COALESCE(dt.egenmelding_hours, 0) AS egenmelding_hours,
        COALESCE(dt.sykemelding_hours, 0) AS sykemelding_hours,
        COALESCE(dt.absence_shifts, 0) AS absence_shifts,
        COALESCE(dt.egenmelding_shifts, 0) AS egenmelding_shifts,
        COALESCE(dt.employer_borne_cost, 0) AS employer_borne_cost,
        COALESCE(dt.nav_borne_cost, 0) AS nav_borne_cost
    FROM {TARGET_SCHEMA}.daily_location_labor dl
    LEFT JOIN daily_totals dt
        ON dt.customer_id = dl.customer_id
        AND dt.revenue_unit_id = dl.revenue_unit_id
        AND dt.order_date = dl.order_date
    WHERE dl.scheduled_hours > 0
),
-- Per-location trailing windows
trailing_windows AS (
    SELECT
        lwa.customer_id,
        lwa.revenue_unit_id,
        db.latest_date,
        -- 28-day totals
        SUM(CASE WHEN lwa.order_date > db.latest_date - INTERVAL '28 days'
            THEN lwa.absence_hours ELSE 0 END) AS abs_hours_28d,
        SUM(CASE WHEN lwa.order_date > db.latest_date - INTERVAL '28 days'
            THEN lwa.scheduled_hours ELSE 0 END) AS sched_hours_28d,
        SUM(CASE WHEN lwa.order_date > db.latest_date - INTERVAL '28 days'
            THEN lwa.egenmelding_hours ELSE 0 END) AS egen_hours_28d,
        SUM(CASE WHEN lwa.order_date > db.latest_date - INTERVAL '28 days'
            THEN lwa.sykemelding_hours ELSE 0 END) AS syke_hours_28d,
        SUM(CASE WHEN lwa.order_date > db.latest_date - INTERVAL '28 days'
            THEN lwa.egenmelding_shifts ELSE 0 END) AS egen_shifts_28d,
        SUM(CASE WHEN lwa.order_date > db.latest_date - INTERVAL '28 days'
            THEN lwa.employer_borne_cost ELSE 0 END) AS employer_cost_28d,
        SUM(CASE WHEN lwa.order_date > db.latest_date - INTERVAL '28 days'
            THEN lwa.nav_borne_cost ELSE 0 END) AS nav_cost_28d,
        -- 90-day totals
        SUM(CASE WHEN lwa.order_date > db.latest_date - INTERVAL '90 days'
            THEN lwa.absence_hours ELSE 0 END) AS abs_hours_90d,
        SUM(CASE WHEN lwa.order_date > db.latest_date - INTERVAL '90 days'
            THEN lwa.scheduled_hours ELSE 0 END) AS sched_hours_90d,
        SUM(CASE WHEN lwa.order_date > db.latest_date - INTERVAL '90 days'
            THEN lwa.employer_borne_cost ELSE 0 END) AS employer_cost_90d,
        -- 365-day totals
        SUM(CASE WHEN lwa.order_date > db.latest_date - INTERVAL '365 days'
            THEN lwa.absence_hours ELSE 0 END) AS abs_hours_365d,
        SUM(CASE WHEN lwa.order_date > db.latest_date - INTERVAL '365 days'
            THEN lwa.scheduled_hours ELSE 0 END) AS sched_hours_365d
    FROM labor_with_absence lwa
    CROSS JOIN date_bounds db
    WHERE lwa.order_date > db.latest_date - INTERVAL '365 days'
    GROUP BY lwa.customer_id, lwa.revenue_unit_id, db.latest_date
),
-- Compute rates
with_rates AS (
    SELECT
        t.customer_id,
        t.revenue_unit_id,
        -- Sick rates
        CASE WHEN t.sched_hours_28d > 0
            THEN ROUND(t.abs_hours_28d / t.sched_hours_28d * 100, 2) ELSE NULL END
            AS trailing_28d_sick_rate_pct,
        CASE WHEN t.sched_hours_90d > 0
            THEN ROUND(t.abs_hours_90d / t.sched_hours_90d * 100, 2) ELSE NULL END
            AS trailing_90d_sick_rate_pct,
        CASE WHEN t.sched_hours_365d > 0
            THEN ROUND(t.abs_hours_365d / t.sched_hours_365d * 100, 2) ELSE NULL END
            AS trailing_365d_sick_rate_pct,
        -- Category breakdown (28d)
        CASE WHEN t.sched_hours_28d > 0
            THEN ROUND(t.egen_hours_28d / t.sched_hours_28d * 100, 2) ELSE NULL END
            AS egenmelding_rate_pct_28d,
        CASE WHEN t.sched_hours_28d > 0
            THEN ROUND(t.syke_hours_28d / t.sched_hours_28d * 100, 2) ELSE NULL END
            AS sykemelding_rate_pct_28d,
        t.egen_shifts_28d AS egenmelding_episodes_28d,
        -- Costs
        ROUND(t.employer_cost_28d, 2) AS employer_borne_cost_28d,
        ROUND(t.employer_cost_90d, 2) AS employer_borne_cost_90d,
        ROUND(t.nav_cost_28d, 2) AS nav_borne_cost_28d
    FROM trailing_windows t
    WHERE t.sched_hours_28d > 0  -- only locations with recent scheduled hours
),
-- Fleet average
fleet AS (
    SELECT
        wr.customer_id,
        AVG(wr.trailing_28d_sick_rate_pct) AS fleet_avg_sick_rate_pct
    FROM with_rates wr
    WHERE wr.trailing_28d_sick_rate_pct IS NOT NULL
    GROUP BY wr.customer_id
)
SELECT
    wr.customer_id,
    wr.revenue_unit_id,
    ru.name AS location_name,
    wr.trailing_28d_sick_rate_pct,
    wr.trailing_90d_sick_rate_pct,
    wr.trailing_365d_sick_rate_pct,
    -- Drift: positive = worsening (28d rate higher than 90d)
    ROUND(COALESCE(wr.trailing_28d_sick_rate_pct, 0)
        - COALESCE(wr.trailing_90d_sick_rate_pct, 0), 2)
        AS sick_rate_drift_28d_vs_90d,
    wr.egenmelding_rate_pct_28d,
    wr.sykemelding_rate_pct_28d,
    wr.egenmelding_episodes_28d,
    wr.employer_borne_cost_28d,
    wr.employer_borne_cost_90d,
    wr.nav_borne_cost_28d,
    ROUND(f.fleet_avg_sick_rate_pct, 2) AS fleet_avg_sick_rate_pct,
    ROUND(COALESCE(wr.trailing_28d_sick_rate_pct, 0)
        - COALESCE(f.fleet_avg_sick_rate_pct, 0), 2)
        AS sick_rate_vs_fleet_delta
FROM with_rates wr
JOIN {SOURCE_DB}.munu.revenue_units ru
    ON ru.customer_id = wr.customer_id
    AND ru.revenue_unit_id = wr.revenue_unit_id
LEFT JOIN fleet f
    ON f.customer_id = wr.customer_id;
