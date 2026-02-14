-- Config parameters: grunnbeløp, overtime threshold, staffing targets
-- Stores configurable values with validity periods

CREATE OR REPLACE TABLE {TARGET_SCHEMA}.config_parameters (
    param_key    VARCHAR NOT NULL,
    param_value  DECIMAL(18,2) NOT NULL,
    valid_from   DATE NOT NULL,
    valid_to     DATE,
    description  VARCHAR,
    PRIMARY KEY (param_key, valid_from)
);

-- Seed values
INSERT INTO {TARGET_SCHEMA}.config_parameters VALUES
    ('grunnbelop', 124028, '2024-05-01', '2025-04-30',
     'Grunnbeløpet (1G) in NOK. 6G ≈ 744,168 NOK/year — NAV reimbursement cap.'),
    ('grunnbelop', 130232, '2025-05-01', NULL,
     'Grunnbeløpet (1G) in NOK — 2025 value.'),
    ('overtime_threshold_hours', 7.5, '2020-01-01', NULL,
     'Per-shift overtime threshold in hours. Hours above this = overtime.'),
    ('overtime_multiplier', 1.5, '2020-01-01', NULL,
     'Overtime pay multiplier (1.5x normal rate).'),
    ('target_transactions_per_staff', 10, '2020-01-01', NULL,
     'Target transactions per staff per hour. Used for staffing recommendations.'),
    ('standard_work_hours_year', 1950, '2020-01-01', NULL,
     'Standard Norwegian work hours per year. Used to estimate annual salary from hourly rate.');
