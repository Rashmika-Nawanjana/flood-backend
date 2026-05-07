-- Schema updates: link rivers to zones and update flood predictions to zone-based JSON

-- 1) Link zones to rivers
ALTER TABLE IF EXISTS zones
    ADD COLUMN IF NOT EXISTS river_id BIGINT;

ALTER TABLE IF EXISTS zones
    ADD COLUMN IF NOT EXISTS prev_zone_id VARCHAR(64),
    ADD COLUMN IF NOT EXISTS next_zone_id VARCHAR(64);

ALTER TABLE IF EXISTS zones
    ALTER COLUMN river_id SET NOT NULL,

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'zones')
        AND EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'rivers')
        AND NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'zones_river_id_fkey'
        ) THEN
        ALTER TABLE zones
            ADD CONSTRAINT zones_river_id_fkey
            FOREIGN KEY (river_id) REFERENCES rivers(river_id) ON DELETE RESTRICT;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'zones')
        AND NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'zones_prev_zone_id_fkey'
        ) THEN
        ALTER TABLE zones
            ADD CONSTRAINT zones_prev_zone_id_fkey
            FOREIGN KEY (prev_zone_id) REFERENCES zones(zone_id) ON DELETE RESTRICT;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'zones')
        AND NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'zones_next_zone_id_fkey'
        ) THEN
        ALTER TABLE zones
            ADD CONSTRAINT zones_next_zone_id_fkey
            FOREIGN KEY (next_zone_id) REFERENCES zones(zone_id) ON DELETE RESTRICT;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_zones_river_id ON zones(river_id);
CREATE INDEX IF NOT EXISTS idx_zones_prev_zone_id ON zones(prev_zone_id);
CREATE INDEX IF NOT EXISTS idx_zones_next_zone_id ON zones(next_zone_id);

-- 2) Update flood_predictions to zone-based JSON water levels
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'flood_predictions') THEN
        IF EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'flood_predictions_station_id_fkey'
        ) THEN
            ALTER TABLE flood_predictions
                DROP CONSTRAINT flood_predictions_station_id_fkey;
        END IF;

        ALTER TABLE flood_predictions
            DROP COLUMN IF EXISTS station_id,
            DROP COLUMN IF EXISTS predicted_level,
            DROP COLUMN IF EXISTS start_time,
            DROP COLUMN IF EXISTS end_time,
            DROP COLUMN IF EXISTS confidence,
            ADD COLUMN IF NOT EXISTS zone_id VARCHAR(64),
            ADD COLUMN IF NOT EXISTS water_level JSONB;
    ELSE
        CREATE TABLE flood_predictions (
            prediction_id BIGSERIAL PRIMARY KEY,
            zone_id VARCHAR(64) NOT NULL,
            model_id BIGINT NOT NULL REFERENCES model_metadata(model_id) ON DELETE RESTRICT,
            water_level JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    END IF;
END $$;

ALTER TABLE IF EXISTS flood_predictions
    ALTER COLUMN zone_id SET NOT NULL,
    ALTER COLUMN water_level SET NOT NULL;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'flood_predictions')
        AND EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'zones')
        AND NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'flood_predictions_zone_id_fkey'
        ) THEN
        ALTER TABLE flood_predictions
            ADD CONSTRAINT flood_predictions_zone_id_fkey
            FOREIGN KEY (zone_id) REFERENCES zones(zone_id) ON DELETE CASCADE;
    END IF;
END $$;

DROP INDEX IF EXISTS idx_predictions_station_id;
CREATE INDEX IF NOT EXISTS idx_predictions_zone_id ON flood_predictions(zone_id);
CREATE INDEX IF NOT EXISTS idx_predictions_model_id ON flood_predictions(model_id);
