-- Daypart configuration: time-of-day buckets for revenue analysis

CREATE OR REPLACE TABLE {TARGET_SCHEMA}.daypart_config (
    daypart_name  VARCHAR NOT NULL PRIMARY KEY,
    hour_start    INTEGER NOT NULL,
    hour_end      INTEGER NOT NULL,
    sort_order    INTEGER NOT NULL
);

INSERT INTO {TARGET_SCHEMA}.daypart_config VALUES
    ('Morning',   6,  11, 1),
    ('Lunch',     11, 14, 2),
    ('Afternoon', 14, 17, 3),
    ('Evening',   17, 22, 4);
