-- Hydrology monitoring schema
-- PostgreSQL-compatible DDL

CREATE TABLE IF NOT EXISTS rivers (
    id BIGINT PRIMARY KEY,
    river_name VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS stations (
    id BIGINT PRIMARY KEY,
    latitude DECIMAL(9,6) NOT NULL,
    longitude DECIMAL(9,6) NOT NULL,
    river_id BIGINT NOT NULL,
    basin_size DECIMAL(12,2) NOT NULL,
    slope DECIMAL(8,4) NOT NULL,
    elevation DECIMAL(10,2) NOT NULL,
    CONSTRAINT fk_stations_river
        FOREIGN KEY (river_id)
        REFERENCES rivers (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT chk_stations_latitude
        CHECK (latitude BETWEEN -90 AND 90),
    CONSTRAINT chk_stations_longitude
        CHECK (longitude BETWEEN -180 AND 180),
    CONSTRAINT chk_stations_basin_size
        CHECK (basin_size > 0),
    CONSTRAINT chk_stations_slope
        CHECK (slope >= 0)
);

CREATE TABLE IF NOT EXISTS sensors (
    id BIGINT PRIMARY KEY,
    station_id BIGINT NOT NULL,
    sensor_type VARCHAR(100) NOT NULL,
    CONSTRAINT fk_sensors_station
        FOREIGN KEY (station_id)
        REFERENCES stations (id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

-- Helpful indexes for join/filter performance
CREATE INDEX IF NOT EXISTS idx_stations_river_id ON stations (river_id);
CREATE INDEX IF NOT EXISTS idx_sensors_station_id ON sensors (station_id);
CREATE INDEX IF NOT EXISTS idx_sensors_sensor_type ON sensors (sensor_type);
