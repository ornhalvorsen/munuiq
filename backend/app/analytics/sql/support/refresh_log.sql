-- Refresh log: pipeline audit trail
-- DuckDB uses INTEGER PRIMARY KEY for auto-increment (rowid alias)

CREATE TABLE IF NOT EXISTS {TARGET_SCHEMA}.refresh_log (
    id            INTEGER PRIMARY KEY,
    table_name    VARCHAR NOT NULL,
    started_at    TIMESTAMP NOT NULL DEFAULT current_timestamp,
    finished_at   TIMESTAMP,
    duration_ms   INTEGER,
    row_count     INTEGER,
    status        VARCHAR NOT NULL DEFAULT 'running',
    error_message VARCHAR,
    mode          VARCHAR
);
