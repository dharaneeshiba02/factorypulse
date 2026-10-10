-- FactoryPulse local development schema.
-- Run on a new TimescaleDB volume or apply through a reviewed migration.

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS machine_classes (
    machine_class TEXT PRIMARY KEY,
    description TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO machine_classes (machine_class, description) VALUES
    ('CNC_Mill', 'Computer numerical control milling machine'),
    ('Turbofan', 'Turbofan engine'),
    ('Bearing_Rig', 'Bearing test rig'),
    ('Centrifugal_Pump', 'Centrifugal pump'),
    ('unclassified', 'Machine class not yet assigned')
ON CONFLICT (machine_class) DO NOTHING;

CREATE TABLE IF NOT EXISTS assets (
    machine_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    machine_class TEXT NOT NULL DEFAULT 'unclassified',
    asset_type TEXT NOT NULL DEFAULT 'unclassified',
    location TEXT NOT NULL DEFAULT 'plant-1',
    install_date DATE NOT NULL DEFAULT CURRENT_DATE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add fields when this initialization file is reapplied to an older local DB.
ALTER TABLE assets ADD COLUMN IF NOT EXISTS machine_class TEXT;
ALTER TABLE assets ADD COLUMN IF NOT EXISTS asset_type TEXT;
ALTER TABLE assets ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

UPDATE assets
SET machine_class = COALESCE(NULLIF(machine_class, ''), NULLIF(asset_type, ''), 'unclassified'),
    asset_type = COALESCE(NULLIF(asset_type, ''), NULLIF(machine_class, ''), 'unclassified')
WHERE machine_class IS NULL OR asset_type IS NULL;

ALTER TABLE assets ALTER COLUMN machine_class SET DEFAULT 'unclassified';
ALTER TABLE assets ALTER COLUMN machine_class SET NOT NULL;
ALTER TABLE assets ALTER COLUMN asset_type SET DEFAULT 'unclassified';
ALTER TABLE assets ALTER COLUMN asset_type SET NOT NULL;

CREATE TABLE IF NOT EXISTS sensors (
    sensor_id TEXT PRIMARY KEY,
    machine_id TEXT NOT NULL REFERENCES assets(machine_id) ON DELETE CASCADE,
    sensor TEXT NOT NULL,
    unit TEXT NOT NULL DEFAULT '',
    min_valid DOUBLE PRECISION,
    max_valid DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (machine_id, sensor),
    CHECK (min_valid IS NULL OR max_valid IS NULL OR min_valid <= max_valid)
);

CREATE INDEX IF NOT EXISTS idx_sensors_machine ON sensors (machine_id, sensor);

CREATE TABLE IF NOT EXISTS telemetry (
    time TIMESTAMPTZ NOT NULL,
    machine_id TEXT NOT NULL REFERENCES assets(machine_id),
    sensor VARCHAR(32) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    quality SMALLINT NOT NULL DEFAULT 100 CHECK (quality BETWEEN 0 AND 100)
);

SELECT create_hypertable('telemetry', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_telemetry_machine_time
    ON telemetry (machine_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_sensor_time
    ON telemetry (machine_id, sensor, time DESC);

CREATE TABLE IF NOT EXISTS telemetry_dead_letter (
    id BIGSERIAL PRIMARY KEY,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload JSONB NOT NULL,
    reason_code VARCHAR(64) NOT NULL,
    reason_detail TEXT
);

CREATE INDEX IF NOT EXISTS idx_dead_letter_received_at
    ON telemetry_dead_letter (received_at DESC);

CREATE TABLE IF NOT EXISTS features (
    time TIMESTAMPTZ NOT NULL,
    machine_id TEXT NOT NULL REFERENCES assets(machine_id),
    feature_name VARCHAR(100) NOT NULL,
    feature_value DOUBLE PRECISION NOT NULL,
    window_minutes INTEGER NOT NULL DEFAULT 1
);

SELECT create_hypertable('features', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_features_machine_name_time
    ON features (machine_id, feature_name, time DESC);

CREATE TABLE IF NOT EXISTS feature_snapshots (
    machine_id TEXT PRIMARY KEY REFERENCES assets(machine_id) ON DELETE CASCADE,
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    features JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS predictions (
    id BIGSERIAL,
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    machine_id TEXT NOT NULL REFERENCES assets(machine_id),
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(100) NOT NULL DEFAULT 'unknown',
    prediction_type VARCHAR(30),
    value DOUBLE PRECISION,
    confidence DOUBLE PRECISION,
    rul_hours DOUBLE PRECISION,
    anomaly_score DOUBLE PRECISION,
    failure_prob DOUBLE PRECISION,
    failure_mode TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

SELECT create_hypertable('predictions', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_predictions_machine_time
    ON predictions (machine_id, time DESC);

CREATE TABLE IF NOT EXISTS alerts (
    id BIGSERIAL PRIMARY KEY,
    machine_id TEXT NOT NULL REFERENCES assets(machine_id),
    severity VARCHAR(16) NOT NULL
        CHECK (severity IN ('info', 'warn', 'warning', 'critical')),
    fault_type VARCHAR(64) NOT NULL DEFAULT 'anomaly',
    title TEXT NOT NULL DEFAULT '',
    detail TEXT,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    acknowledged_by TEXT,
    acked_by INTEGER,
    acknowledged_at TIMESTAMPTZ,
    status VARCHAR(16) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'acked', 'resolved')),
    dedup_key VARCHAR(200),
    prediction_id BIGINT,
    model_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_alerts_machine_status
    ON alerts (machine_id, status);
CREATE INDEX IF NOT EXISTS idx_alerts_opened_at
    ON alerts (opened_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_alerts_open_dedup
    ON alerts (machine_id, dedup_key) WHERE status = 'open' AND dedup_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS health_scores (
    time TIMESTAMPTZ NOT NULL,
    machine_id TEXT NOT NULL REFERENCES assets(machine_id),
    score DOUBLE PRECISION NOT NULL CHECK (score BETWEEN 0 AND 100),
    anomaly_contrib DOUBLE PRECISION,
    rul_contrib DOUBLE PRECISION,
    alert_contrib DOUBLE PRECISION,
    thermal_contrib DOUBLE PRECISION,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (time, machine_id)
);

SELECT create_hypertable('health_scores', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_health_scores_machine_time
    ON health_scores (machine_id, time DESC);

CREATE TABLE IF NOT EXISTS users (
    user_id BIGSERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(32) NOT NULL CHECK (
        role IN ('technician', 'engineer', 'manager', 'data_scientist', 'admin')
    ),
    full_name VARCHAR(200) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS work_orders (
    work_order_id BIGSERIAL PRIMARY KEY,
    alert_id BIGINT UNIQUE REFERENCES alerts(id),
    machine_id TEXT NOT NULL REFERENCES assets(machine_id),
    title TEXT NOT NULL,
    draft_md TEXT NOT NULL DEFAULT '',
    diagnosis TEXT,
    recommended_action TEXT,
    parts_needed JSONB NOT NULL DEFAULT '[]'::jsonb,
    citations JSONB NOT NULL DEFAULT '[]'::jsonb,
    priority VARCHAR(16),
    status VARCHAR(16) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'approved', 'rejected')),
    created_by BIGINT REFERENCES users(user_id),
    approved_by BIGINT REFERENCES users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    action VARCHAR(64) NOT NULL,
    entity_type VARCHAR(64) NOT NULL,
    entity_id VARCHAR(128),
    at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    detail JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_audit_log_at ON audit_log (at DESC);

CREATE TABLE IF NOT EXISTS drift_reports (
    id BIGSERIAL PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    model_name VARCHAR(100),
    model_version VARCHAR(100),
    feature_name VARCHAR(100),
    metric_type VARCHAR(30),
    metric_value DOUBLE PRECISION,
    threshold DOUBLE PRECISION,
    is_drift BOOLEAN,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_drift_reports_time ON drift_reports (time DESC);

CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    machine_id,
    sensor,
    AVG(value) AS avg_value,
    MIN(value) AS min_value,
    MAX(value) AS max_value,
    STDDEV(value) AS std_value,
    COUNT(*) AS sample_count
FROM telemetry
GROUP BY bucket, machine_id, sensor
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_1hr
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    machine_id,
    sensor,
    AVG(value) AS avg_value,
    MIN(value) AS min_value,
    MAX(value) AS max_value,
    STDDEV(value) AS std_value,
    COUNT(*) AS sample_count
FROM telemetry
GROUP BY bucket, machine_id, sensor
WITH NO DATA;

SELECT add_retention_policy('telemetry', INTERVAL '90 days', if_not_exists => TRUE);
SELECT add_retention_policy('predictions', INTERVAL '365 days', if_not_exists => TRUE);
SELECT add_continuous_aggregate_policy(
    'telemetry_1min',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE
);
SELECT add_continuous_aggregate_policy(
    'telemetry_1hr',
    start_offset => INTERVAL '2 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);
