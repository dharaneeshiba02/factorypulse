-- ============================================
-- FactoryPulse Database Schema
-- TimescaleDB + PostgreSQL
-- ============================================
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ASSET REGISTRY
CREATE TABLE IF NOT EXISTS machines (
    machine_id VARCHAR(50) PRIMARY KEY,
    machine_class VARCHAR(100) NOT NULL,
    location VARCHAR(200),
    install_date DATE,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sensors (
    sensor_id VARCHAR(100) PRIMARY KEY,
    machine_id VARCHAR(50) REFERENCES machines(machine_id),
    sensor_type VARCHAR(50) NOT NULL,
    unit VARCHAR(20),
    min_valid DOUBLE PRECISION,
    max_valid DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- TELEMETRY (TimescaleDB Hypertable)
CREATE TABLE IF NOT EXISTS telemetry (
    ts TIMESTAMPTZ NOT NULL,
    machine_id VARCHAR(50) NOT NULL,
    sensor_id VARCHAR(100) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    quality SMALLINT DEFAULT 0 -- 0=good, 1=suspect, 2=bad
);
SELECT create_hypertable('telemetry', 'ts',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_telemetry_machine
    ON telemetry (machine_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_sensor
    ON telemetry (sensor_id, ts DESC);

-- Continuous aggregate for dashboard queries
CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', ts) AS bucket,
    machine_id,
    sensor_id,
    AVG(value) AS avg_val,
    MIN(value) AS min_val,
    MAX(value) AS max_val,
    STDDEV(value) AS std_val,
    COUNT(*) AS sample_count
FROM telemetry
GROUP BY bucket, machine_id, sensor_id;

-- Retention: raw data kept 90 days, aggregates indefinite
SELECT add_retention_policy('telemetry', INTERVAL '90 days',
    if_not_exists => TRUE);

-- DEAD LETTER (Ingestion Failures)
CREATE TABLE IF NOT EXISTS dead_letter (
    id BIGSERIAL PRIMARY KEY,
    received_at TIMESTAMPTZ DEFAULT NOW(),
    raw_payload JSONB NOT NULL,
    reason_code VARCHAR(50) NOT NULL,
    reason_detail TEXT
);

-- FEATURES (Materialized for ML)
CREATE TABLE IF NOT EXISTS features (
    ts TIMESTAMPTZ NOT NULL,
    machine_id VARCHAR(50) NOT NULL,
    feature_name VARCHAR(100) NOT NULL,
    feature_value DOUBLE PRECISION NOT NULL,
    window_minutes INT NOT NULL DEFAULT 60
);
SELECT create_hypertable('features', 'ts',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_features_lookup
    ON features (machine_id, feature_name, ts DESC);

-- PREDICTIONS
CREATE TABLE IF NOT EXISTS predictions (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ DEFAULT NOW(),
    machine_id VARCHAR(50) REFERENCES machines(machine_id),
    prediction_type VARCHAR(30) NOT NULL, -- 'anomaly','rul','fault_class'
    value DOUBLE PRECISION NOT NULL,
    confidence DOUBLE PRECISION,
    model_version VARCHAR(100),
    model_name VARCHAR(100),
    details JSONB DEFAULT '{}'::jsonb
);

-- ALERTS
CREATE TABLE IF NOT EXISTS alerts (
    alert_id BIGSERIAL PRIMARY KEY,
    machine_id VARCHAR(50) REFERENCES machines(machine_id),
    severity VARCHAR(20) NOT NULL, -- 'INFO','WARN','CRITICAL'
    alert_type VARCHAR(50) NOT NULL, -- 'anomaly','rul_low','fault_detected'
    title TEXT NOT NULL,
    detail TEXT,
    prediction_id BIGINT REFERENCES predictions(id),
    opened_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    acknowledged_by VARCHAR(100),
    status VARCHAR(20) DEFAULT 'open', -- 'open','ack','resolved'
    dedup_key VARCHAR(200),
    model_snapshot JSONB
);
CREATE INDEX IF NOT EXISTS idx_alerts_open
    ON alerts (machine_id, status) WHERE status = 'open';

-- HEALTH SCORES
CREATE TABLE IF NOT EXISTS health_scores (
    ts TIMESTAMPTZ NOT NULL,
    machine_id VARCHAR(50) NOT NULL,
    score DOUBLE PRECISION NOT NULL, -- 0-100
    anomaly_contrib DOUBLE PRECISION,
    rul_contrib DOUBLE PRECISION,
    alert_contrib DOUBLE PRECISION,
    details JSONB
);
SELECT create_hypertable('health_scores', 'ts',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- WORK ORDERS (Copilot-generated)
CREATE TABLE IF NOT EXISTS work_orders (
    work_order_id BIGSERIAL PRIMARY KEY,
    alert_id BIGINT REFERENCES alerts(alert_id),
    machine_id VARCHAR(50) REFERENCES machines(machine_id),
    title TEXT NOT NULL,
    diagnosis TEXT,
    recommended_action TEXT,
    parts_needed JSONB,
    citations JSONB, -- [{source, page, text_snippet}]
    priority VARCHAR(20),
    status VARCHAR(20) DEFAULT 'draft',
    created_by VARCHAR(100) DEFAULT 'copilot',
    approved_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- AUTH & AUDIT
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(30) NOT NULL, -- 'technician','engineer','manager','data_scientist','admin'
    full_name VARCHAR(200),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ DEFAULT NOW(),
    user_id INT,
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),
    detail JSONB
);

-- DRIFT MONITORING
CREATE TABLE IF NOT EXISTS drift_reports (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ DEFAULT NOW(),
    model_name VARCHAR(100),
    model_version VARCHAR(100),
    feature_name VARCHAR(100),
    metric_type VARCHAR(30), -- 'psi','ks_stat','score_distribution'
    metric_value DOUBLE PRECISION,
    threshold DOUBLE PRECISION,
    is_drift BOOLEAN,
    detail JSONB
);
