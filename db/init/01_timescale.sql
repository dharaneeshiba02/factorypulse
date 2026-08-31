-- ============================================================
-- FactoryPulse — TimescaleDB Schema Initialization
-- ============================================================

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================
-- 1. Assets table — registered machines / equipment
-- ============================================================
CREATE TABLE IF NOT EXISTS assets (
    machine_id   TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    asset_type   TEXT NOT NULL DEFAULT 'turbofan',
    location     TEXT NOT NULL DEFAULT 'plant-1',
    install_date DATE NOT NULL DEFAULT CURRENT_DATE,
    metadata     JSONB DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 2. Telemetry hypertable — raw sensor readings
-- ============================================================
CREATE TABLE IF NOT EXISTS telemetry (
    time         TIMESTAMPTZ NOT NULL,
    machine_id   TEXT        NOT NULL REFERENCES assets(machine_id),
    sensor       TEXT        NOT NULL,
    value        DOUBLE PRECISION NOT NULL,
    quality      INTEGER     NOT NULL DEFAULT 100 CHECK (quality BETWEEN 0 AND 100)
);

SELECT create_hypertable('telemetry', 'time', if_not_exists => TRUE);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_telemetry_machine
    ON telemetry (machine_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_sensor
    ON telemetry (machine_id, sensor, time DESC);

-- ============================================================
-- 3. Predictions table — model output storage
-- ============================================================
CREATE TABLE IF NOT EXISTS predictions (
    time           TIMESTAMPTZ NOT NULL,
    machine_id     TEXT        NOT NULL REFERENCES assets(machine_id),
    model_name     TEXT        NOT NULL,
    model_version  TEXT        NOT NULL DEFAULT 'latest',
    rul_hours      DOUBLE PRECISION,
    anomaly_score  DOUBLE PRECISION,
    failure_prob   DOUBLE PRECISION,
    failure_mode   TEXT,
    metadata       JSONB DEFAULT '{}'::jsonb
);

SELECT create_hypertable('predictions', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_predictions_machine
    ON predictions (machine_id, time DESC);

-- ============================================================
-- 4. Alerts table — maintenance alerts
-- ============================================================
CREATE TABLE IF NOT EXISTS alerts (
    id             SERIAL,
    time           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    machine_id     TEXT        NOT NULL REFERENCES assets(machine_id),
    severity       TEXT        NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    alert_type     TEXT        NOT NULL DEFAULT 'anomaly',
    message        TEXT        NOT NULL,
    acknowledged   BOOLEAN     NOT NULL DEFAULT FALSE,
    acknowledged_by TEXT,
    acknowledged_at TIMESTAMPTZ,
    metadata       JSONB DEFAULT '{}'::jsonb
);

SELECT create_hypertable('alerts', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_alerts_unack
    ON alerts (machine_id, time DESC) WHERE acknowledged = FALSE;

-- ============================================================
-- 5. Feature snapshots — latest computed features per machine
-- ============================================================
CREATE TABLE IF NOT EXISTS feature_snapshots (
    time         TIMESTAMPTZ NOT NULL,
    machine_id   TEXT        NOT NULL REFERENCES assets(machine_id),
    features     JSONB       NOT NULL,
    UNIQUE (machine_id)
);

-- ============================================================
-- 6. Continuous Aggregates — 1-minute rollups
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    machine_id,
    sensor,
    AVG(value)    AS avg_value,
    MIN(value)    AS min_value,
    MAX(value)    AS max_value,
    STDDEV(value) AS std_value,
    COUNT(*)      AS sample_count
FROM telemetry
GROUP BY bucket, machine_id, sensor
WITH NO DATA;

-- ============================================================
-- 7. Continuous Aggregates — 1-hour rollups
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_1hr
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    machine_id,
    sensor,
    AVG(value)    AS avg_value,
    MIN(value)    AS min_value,
    MAX(value)    AS max_value,
    STDDEV(value) AS std_value,
    COUNT(*)      AS sample_count
FROM telemetry
GROUP BY bucket, machine_id, sensor
WITH NO DATA;

-- ============================================================
-- 8. Retention policies
-- ============================================================
-- Raw telemetry: keep 90 days
SELECT add_retention_policy('telemetry', INTERVAL '90 days', if_not_exists => TRUE);

-- Predictions: keep 1 year
SELECT add_retention_policy('predictions', INTERVAL '365 days', if_not_exists => TRUE);

-- Alerts: keep 1 year
SELECT add_retention_policy('alerts', INTERVAL '365 days', if_not_exists => TRUE);

-- Refresh policies for continuous aggregates
SELECT add_continuous_aggregate_policy('telemetry_1min',
    start_offset    => INTERVAL '3 hours',
    end_offset      => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists   => TRUE
);

SELECT add_continuous_aggregate_policy('telemetry_1hr',
    start_offset    => INTERVAL '2 days',
    end_offset      => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists   => TRUE
);
