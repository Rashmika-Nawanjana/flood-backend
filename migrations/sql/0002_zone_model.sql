-- Zone-centric schema additions for sensor and zone microservices
-- Idempotent: safe to run multiple times (uses IF NOT EXISTS and guards)

-- 1) Zones (canonical spatial/risk entity)
CREATE TABLE IF NOT EXISTS zones (
    zone_id VARCHAR(64) PRIMARY KEY,
    zone_name VARCHAR(150) NOT NULL,
    description TEXT,
    risk_level VARCHAR(20),
    risk_score NUMERIC(6,4),
    color_code VARCHAR(20),
    population_at_risk INTEGER DEFAULT 0 CHECK (population_at_risk >= 0),
    active_alerts INTEGER DEFAULT 0 CHECK (active_alerts >= 0),
    last_updated TIMESTAMPTZ,
    geometry JSONB,
    current_conditions JSONB,
    prediction JSONB
);

-- 2) Sensor nodes (device registry used by sensor-service)
CREATE TABLE IF NOT EXISTS sensor_nodes (
    sensor_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(200),
    zone_id VARCHAR(64) REFERENCES zones(zone_id) ON DELETE SET NULL,
    lat NUMERIC(9,6) CHECK (lat BETWEEN -90 AND 90),
    lng NUMERIC(9,6) CHECK (lng BETWEEN -180 AND 180),
    address TEXT,
    installed_date DATE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    firmware_version VARCHAR(100),
    last_maintenance DATE,
    list_status_key VARCHAR(100),
    list_thresholds_key VARCHAR(100),
    watch_m NUMERIC(8,3),
    advisory_m NUMERIC(8,3),
    warning_m NUMERIC(8,3),
    critical_m NUMERIC(8,3)
);

-- 3) Zone shelters: contains shelter metadata associated with a zone
CREATE TABLE IF NOT EXISTS zone_shelters (
    shelter_id VARCHAR(64) PRIMARY KEY,
    zone_id VARCHAR(64) REFERENCES zones(zone_id) ON DELETE CASCADE,
    name VARCHAR(200),
    capacity INTEGER,
    current_occupancy INTEGER DEFAULT 0,
    lat NUMERIC(9,6),
    lng NUMERIC(9,6),
    distance_km NUMERIC(8,3),
    contact_number VARCHAR(50),
    status VARCHAR(30)
);

-- 4) Anomalies (sensor-detected events)
CREATE TABLE IF NOT EXISTS anomalies (
    anomaly_id VARCHAR(64) PRIMARY KEY,
    sensor_id VARCHAR(64) REFERENCES sensor_nodes(sensor_id) ON DELETE SET NULL,
    zone_id VARCHAR(64) REFERENCES zones(zone_id) ON DELETE SET NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    type VARCHAR(100),
    severity VARCHAR(20),
    anomaly_score NUMERIC(5,4),
    reading JSONB,
    status VARCHAR(20) DEFAULT 'UNRESOLVED'
);

-- 5) Helpful indexes
CREATE INDEX IF NOT EXISTS idx_zones_zone_name ON zones(zone_name);
CREATE INDEX IF NOT EXISTS idx_sensor_nodes_zone_id ON sensor_nodes(zone_id);
CREATE INDEX IF NOT EXISTS idx_zone_shelters_zone_id ON zone_shelters(zone_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_sensor_id ON anomalies(sensor_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_zone_id ON anomalies(zone_id);

-- 6) Drop legacy tables (no production data to preserve)
DROP TABLE IF EXISTS sensors CASCADE;
DROP TABLE IF EXISTS station CASCADE;
DROP TABLE IF EXISTS shelters CASCADE;
DROP TABLE IF EXISTS evacuation_routes CASCADE;
