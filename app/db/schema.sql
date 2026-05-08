-- PostgreSQL schema for flood monitoring system

-- 1) Master tables
CREATE TABLE IF NOT EXISTS rivers (
    river_id BIGSERIAL PRIMARY KEY,
    river_name VARCHAR(150) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS station (
    station_id BIGSERIAL PRIMARY KEY,
    station_name VARCHAR(150) NOT NULL,
    river_id BIGINT NOT NULL REFERENCES rivers(river_id) ON DELETE RESTRICT,
    longitude NUMERIC(9, 6) NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    latitude NUMERIC(9, 6) NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    risk_threshold_water_level NUMERIC(8, 2) NOT NULL CHECK (risk_threshold_water_level >= 0),
    population_count INTEGER NOT NULL CHECK (population_count >= 0)
);

CREATE TABLE IF NOT EXISTS shelters (
    shelter_id BIGSERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    capacity INTEGER NOT NULL CHECK (capacity >= 0)
);

CREATE TABLE IF NOT EXISTS model_metadata (
    model_id BIGSERIAL PRIMARY KEY,
    version VARCHAR(50) NOT NULL,
    accuracy NUMERIC(5, 4) NOT NULL CHECK (accuracy BETWEEN 0 AND 1),
    trained_at TIMESTAMPTZ NOT NULL,
    deployed_at TIMESTAMPTZ
);

-- 2) Operational tables
CREATE TABLE IF NOT EXISTS sensors (
    sensor_id BIGSERIAL PRIMARY KEY,
    station_id BIGINT NOT NULL REFERENCES station(station_id) ON DELETE CASCADE,
    sensor_type VARCHAR(100) NOT NULL,
    installed_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('active', 'inactive', 'maintenance', 'faulty'))
);

CREATE TABLE IF NOT EXISTS flood_predictions (
    prediction_id BIGSERIAL PRIMARY KEY,
    station_id BIGINT NOT NULL REFERENCES station(station_id) ON DELETE CASCADE,
    model_id BIGINT NOT NULL REFERENCES model_metadata(model_id) ON DELETE RESTRICT,
    predicted_level NUMERIC(8, 2) NOT NULL CHECK (predicted_level >= 0),
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    confidence NUMERIC(5, 4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (end_time > start_time)
);

CREATE TABLE IF NOT EXISTS alert_events (
    alert_id BIGSERIAL PRIMARY KEY,
    prediction_id BIGINT NOT NULL REFERENCES flood_predictions(prediction_id) ON DELETE CASCADE,
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS evacuation_routes (
    route_id BIGSERIAL PRIMARY KEY,
    station_id BIGINT NOT NULL REFERENCES station(station_id) ON DELETE CASCADE,
    start_point VARCHAR(255) NOT NULL,
    end_point VARCHAR(255) NOT NULL,
    shelter_id BIGINT NOT NULL REFERENCES shelters(shelter_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS historical_floods (
    event_id BIGSERIAL PRIMARY KEY,
    station_id BIGINT NOT NULL REFERENCES station(station_id) ON DELETE CASCADE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    peak_level NUMERIC(8, 2) NOT NULL CHECK (peak_level >= 0),
    damage_report TEXT,
    CHECK (end_date >= start_date)
);

-- 3) Helpful indexes for foreign keys / query speed
CREATE INDEX IF NOT EXISTS idx_station_river_id ON station(river_id);
CREATE INDEX IF NOT EXISTS idx_sensors_station_id ON sensors(station_id);
CREATE INDEX IF NOT EXISTS idx_predictions_station_id ON flood_predictions(station_id);
CREATE INDEX IF NOT EXISTS idx_predictions_model_id ON flood_predictions(model_id);
CREATE INDEX IF NOT EXISTS idx_alert_events_prediction_id ON alert_events(prediction_id);
CREATE INDEX IF NOT EXISTS idx_routes_station_id ON evacuation_routes(station_id);
CREATE INDEX IF NOT EXISTS idx_routes_shelter_id ON evacuation_routes(shelter_id);
CREATE INDEX IF NOT EXISTS idx_historical_floods_station_id ON historical_floods(station_id);
