-- Upgrade a local volume initialized from the M1 PDF schema to the M2 schema.
-- This script is safe to run repeatedly and keeps existing telemetry records.
CREATE EXTENSION IF NOT EXISTS timescaledb;

DO $$
BEGIN
    IF to_regclass('public.assets') IS NULL
       AND to_regclass('public.machines') IS NOT NULL THEN
        ALTER TABLE machines RENAME TO assets;
    END IF;

    IF to_regclass('public.assets') IS NOT NULL THEN
        ALTER TABLE assets ADD COLUMN IF NOT EXISTS name TEXT;
        ALTER TABLE assets ADD COLUMN IF NOT EXISTS machine_class TEXT;
        ALTER TABLE assets ADD COLUMN IF NOT EXISTS asset_type TEXT;
        ALTER TABLE assets ADD COLUMN IF NOT EXISTS location TEXT;
        ALTER TABLE assets ADD COLUMN IF NOT EXISTS install_date DATE;
        ALTER TABLE assets ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
        ALTER TABLE assets ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
        UPDATE assets SET
            name = COALESCE(NULLIF(name, ''), machine_id),
            machine_class = COALESCE(NULLIF(machine_class, ''), NULLIF(asset_type, ''), 'unclassified'),
            asset_type = COALESCE(NULLIF(asset_type, ''), NULLIF(machine_class, ''), 'unclassified'),
            location = COALESCE(NULLIF(location, ''), 'plant-1'),
            install_date = COALESCE(install_date, CURRENT_DATE),
            metadata = COALESCE(metadata, '{}'::jsonb),
            updated_at = COALESCE(updated_at, NOW());
        ALTER TABLE assets ALTER COLUMN name SET NOT NULL;
        ALTER TABLE assets ALTER COLUMN machine_class SET DEFAULT 'unclassified';
        ALTER TABLE assets ALTER COLUMN machine_class SET NOT NULL;
        ALTER TABLE assets ALTER COLUMN asset_type SET DEFAULT 'unclassified';
        ALTER TABLE assets ALTER COLUMN asset_type SET NOT NULL;
        ALTER TABLE assets ALTER COLUMN location SET DEFAULT 'plant-1';
        ALTER TABLE assets ALTER COLUMN location SET NOT NULL;
        ALTER TABLE assets ALTER COLUMN install_date SET DEFAULT CURRENT_DATE;
        ALTER TABLE assets ALTER COLUMN install_date SET NOT NULL;
        ALTER TABLE assets ALTER COLUMN metadata SET DEFAULT '{}'::jsonb;
        ALTER TABLE assets ALTER COLUMN metadata SET NOT NULL;
        ALTER TABLE assets ALTER COLUMN updated_at SET DEFAULT NOW();
        ALTER TABLE assets ALTER COLUMN updated_at SET NOT NULL;
    END IF;

    IF to_regclass('public.sensors') IS NOT NULL
       AND EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = 'sensors'
             AND column_name = 'sensor_type'
       )
       AND NOT EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = 'sensors'
             AND column_name = 'sensor'
       ) THEN
        ALTER TABLE sensors RENAME COLUMN sensor_type TO sensor;
    END IF;

    IF to_regclass('public.sensors') IS NOT NULL THEN
        ALTER TABLE sensors ADD COLUMN IF NOT EXISTS unit TEXT NOT NULL DEFAULT '';
        ALTER TABLE sensors ADD COLUMN IF NOT EXISTS min_valid DOUBLE PRECISION;
        ALTER TABLE sensors ADD COLUMN IF NOT EXISTS max_valid DOUBLE PRECISION;
        ALTER TABLE sensors ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
        CREATE UNIQUE INDEX IF NOT EXISTS idx_sensors_machine_sensor_unique
            ON sensors (machine_id, sensor);
    END IF;

    IF to_regclass('public.telemetry') IS NOT NULL THEN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'telemetry'
              AND column_name = 'ts'
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'telemetry'
              AND column_name = 'time'
        ) THEN
            ALTER TABLE telemetry RENAME COLUMN ts TO time;
        END IF;
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'telemetry'
              AND column_name = 'sensor_id'
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'telemetry'
              AND column_name = 'sensor'
        ) THEN
            ALTER TABLE telemetry RENAME COLUMN sensor_id TO sensor;
        END IF;
    END IF;

    IF to_regclass('public.dead_letter') IS NOT NULL
       AND to_regclass('public.telemetry_dead_letter') IS NULL THEN
        ALTER TABLE dead_letter RENAME TO telemetry_dead_letter;
    END IF;

    IF to_regclass('public.features') IS NOT NULL
       AND EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = 'features'
             AND column_name = 'ts'
       ) AND NOT EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = 'features'
             AND column_name = 'time'
       ) THEN
        ALTER TABLE features RENAME COLUMN ts TO time;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS machine_classes (
    machine_class TEXT PRIMARY KEY,
    description TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO machine_classes (machine_class, description) VALUES
    ('unclassified', 'Machine class not yet assigned'),
    ('CNC_Mill', 'Computer numerical control milling machine'),
    ('Turbofan', 'Turbofan engine'),
    ('Bearing_Rig', 'Bearing test rig'),
    ('Centrifugal_Pump', 'Centrifugal pump')
ON CONFLICT (machine_class) DO NOTHING;
INSERT INTO machine_classes (machine_class, description)
SELECT DISTINCT machine_class, 'Migrated machine class'
FROM assets
WHERE machine_class IS NOT NULL AND machine_class <> ''
ON CONFLICT (machine_class) DO NOTHING;

DO $$
DECLARE
    quality_check RECORD;
    legacy_quality BOOLEAN := FALSE;
BEGIN
    IF to_regclass('public.telemetry') IS NOT NULL THEN
        SELECT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'public.telemetry'::regclass
              AND contype = 'c'
              AND pg_get_constraintdef(oid) ILIKE '%quality%2%'
        ) INTO legacy_quality;

        IF legacy_quality THEN
            FOR quality_check IN
                SELECT conname FROM pg_constraint
                WHERE conrelid = 'public.telemetry'::regclass
                  AND contype = 'c'
                  AND pg_get_constraintdef(oid) ILIKE '%quality%'
            LOOP
                EXECUTE format('ALTER TABLE telemetry DROP CONSTRAINT %I', quality_check.conname);
            END LOOP;
            UPDATE telemetry SET quality = CASE quality
                WHEN 0 THEN 100 WHEN 1 THEN 50 WHEN 2 THEN 0 ELSE quality END;
        END IF;

        ALTER TABLE telemetry ALTER COLUMN quality SET DEFAULT 100;
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'public.telemetry'::regclass
              AND conname = 'telemetry_quality_percent_check'
        ) THEN
            ALTER TABLE telemetry ADD CONSTRAINT telemetry_quality_percent_check
                CHECK (quality BETWEEN 0 AND 100);
        END IF;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS feature_snapshots (
    machine_id TEXT PRIMARY KEY REFERENCES assets(machine_id) ON DELETE CASCADE,
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    features JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_telemetry_machine_time
    ON telemetry (machine_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_sensor_time
    ON telemetry (machine_id, sensor, time DESC);
CREATE INDEX IF NOT EXISTS idx_features_machine_name_time
    ON features (machine_id, feature_name, time DESC);
