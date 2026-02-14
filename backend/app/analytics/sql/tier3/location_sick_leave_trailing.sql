-- 3.5 Location Sick Leave Trailing (discovery-gated)
-- Grain: customer_id x revenue_unit_id (snapshot)
-- Only populated if 2.8 has data

CREATE OR REPLACE TABLE {TARGET_SCHEMA}.location_sick_leave_trailing (
    customer_id                  INTEGER NOT NULL,
    revenue_unit_id              VARCHAR NOT NULL,
    trailing_28d_sick_rate_pct   DECIMAL(10,2),
    trailing_90d_sick_rate_pct   DECIMAL(10,2),
    trailing_365d_sick_rate_pct  DECIMAL(10,2),
    sick_rate_drift_28d_vs_90d   DECIMAL(10,2),
    egenmelding_rate_pct_28d     DECIMAL(10,2),
    sykemelding_rate_pct_28d     DECIMAL(10,2),
    egenmelding_episodes_28d     INTEGER,
    employer_borne_cost_28d      DECIMAL(18,2),
    employer_borne_cost_90d      DECIMAL(18,2),
    nav_borne_cost_28d           DECIMAL(18,2),
    fleet_avg_sick_rate_pct      DECIMAL(10,2),
    sick_rate_vs_fleet_delta     DECIMAL(10,2)
);

-- Data population (only run if 2.8 has data)
-- {SICK_LEAVE_TRAILING_INSERT}
