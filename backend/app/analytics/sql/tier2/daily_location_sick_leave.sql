-- 2.8 Daily Location Sick Leave (discovery-gated)
-- Grain: customer_id x revenue_unit_id x order_date x absence_type
-- Only populated if discovery confirms absence shift_types exist

-- Create table with stable schema regardless of data availability
CREATE OR REPLACE TABLE {TARGET_SCHEMA}.daily_location_sick_leave (
    customer_id         INTEGER NOT NULL,
    revenue_unit_id     VARCHAR NOT NULL,
    order_date          DATE NOT NULL,
    absence_type        VARCHAR NOT NULL,
    absence_hours       DECIMAL(10,2),
    absence_episodes    INTEGER,
    employees_absent    INTEGER,
    gross_salary_cost   DECIMAL(18,2),
    employer_borne_cost DECIMAL(18,2),
    nav_borne_cost      DECIMAL(18,2)
);

-- Data population (only run if absence data discovered)
-- {SICK_LEAVE_INSERT}
