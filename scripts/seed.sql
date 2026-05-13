-- Mahaweli dev dataset seed data for scripts/seed-dev-data.py

INSERT INTO rivers (river_name)
VALUES ('Mahaweli River');

INSERT INTO zones (
    zone_id,
    zone_name,
    description,
    risk_level,
    risk_score,
    color_code,
    population_at_risk,
    active_alerts,
    river_id,
    prev_zone_id,
    next_zone_id,
    geometry,
    current_conditions,
    prediction,
    last_updated
)
VALUES
(
    'ZONE-M3',
    'Gampola Town Reach',
    'Targeted urban warning zone covering the highly flood-prone Gampola town limits and main bridge',
    'MEDIUM',
    0.34,
    '#FACC15',
    5400,
    0,
    (SELECT river_id FROM rivers WHERE river_name = 'Mahaweli River' LIMIT 1),
    NULL,
    NULL,
    '{"type":"Polygon","coordinates":[[[80.565,7.150],[80.580,7.150],[80.585,7.165],[80.575,7.175],[80.560,7.175],[80.555,7.165],[80.565,7.150]]]}'::jsonb,
    '{"avg_water_level_m":1.3,"flow_velocity_mps":1.0,"trend":"RISING"}'::jsonb,
    '{"predicted_peak_level_m":2.0,"flood_probability_percent":18.0}'::jsonb,
    TIMESTAMPTZ '2026-05-13 00:00:00+00'
),
(
    'ZONE-K1',
    'Kandy Central',
    'The northern Mahaweli river bend through Katugastota, ending just upstream of the Polgolla Barrage',
    'HIGH',
        0.95,
    '#F97316',
    12800,
    2,
    (SELECT river_id FROM rivers WHERE river_name = 'Mahaweli River' LIMIT 1),
    NULL,
    NULL,
    '{"type":"Polygon","coordinates":[[[80.62,7.315],[80.63,7.315],[80.63,7.322],[80.639,7.325],[80.649,7.325],[80.639,7.335],[80.635,7.335],[80.62,7.325],[80.62,7.315]]]}'::jsonb,
    '{"avg_water_level_m":2.2,"max_water_level_m":3.6,"trend":"RISING"}'::jsonb,
        '{"predicted_peak_level_m":3.8,"flood_probability_percent":61.0}'::jsonb,
    TIMESTAMPTZ '2026-05-13 00:00:00+00'
),
(
    'ZONE-X1',
    'Getambe Basin',
    'Confluence and midstream zone downstream of Kandy',
    'CRITICAL',
    0.86,
    '#EF4444',
    14600,
    3,
    (SELECT river_id FROM rivers WHERE river_name = 'Mahaweli River' LIMIT 1),
    NULL,
    NULL,
    '{"type":"Polygon","coordinates":[[[80.59,7.26],[80.59,7.28],[80.6,7.28],[80.61,7.295],[80.615,7.285],[80.607,7.279],[80.61,7.27],[80.595,7.26],[80.59,7.26]]]}'::jsonb,
    '{"avg_water_level_m":2.9,"max_water_level_m":4.8,"trend":"RISING"}'::jsonb,
    '{"predicted_peak_level_m":5.2,"flood_probability_percent":84.0}'::jsonb,
    TIMESTAMPTZ '2026-05-13 00:00:00+00'
),
(
    'ZONE-T1',
    'Mahaweli Lower Delta',
    'The broad lower floodplain and estuary where the Mahaweli empties into Koddiyar Bay',
    'LOW',
    0.56,
    '#22C55E',
    8700,
    1,
    (SELECT river_id FROM rivers WHERE river_name = 'Mahaweli River' LIMIT 1),
    NULL,
    NULL,
    '{"type":"Polygon","coordinates":[[[81.150,8.410],[81.160,8.490],[81.210,8.530],[81.220,8.500],[81.200,8.487],[81.220,8.470],[81.275,8.470],[81.280,8.440],[81.200,8.410],[81.150,8.410]]]}'::jsonb,
    '{"avg_water_level_m":1.8,"flow_velocity_mps":0.7,"trend":"STABLE"}'::jsonb,
    '{"predicted_peak_level_m":1.8,"flood_probability_percent":34.0}'::jsonb,
    TIMESTAMPTZ '2026-05-13 00:00:00+00'
);

UPDATE zones SET prev_zone_id = NULL, next_zone_id = 'ZONE-X1' WHERE zone_id = 'ZONE-M3';
UPDATE zones SET prev_zone_id = 'ZONE-M3', next_zone_id = 'ZONE-K1' WHERE zone_id = 'ZONE-X1';
UPDATE zones SET prev_zone_id = 'ZONE-X1', next_zone_id = 'ZONE-T1' WHERE zone_id = 'ZONE-K1';
UPDATE zones SET prev_zone_id = 'ZONE-K1', next_zone_id = NULL WHERE zone_id = 'ZONE-T1';

INSERT INTO sensor_nodes (
    sensor_id,
    name,
    zone_id,
    lat,
    lng,
    address,
    installed_date,
    is_active,
    firmware_version,
    last_maintenance,
    list_status_key,
    list_thresholds_key,
    watch_m,
    advisory_m,
    warning_m,
    critical_m
)
VALUES
(
    'MR-M3-001',
    'Gampola Bridge Gauge',
    'ZONE-M3',
    7.1625,
    80.5732,
    'Gampola-Nawalapitiya Road Bridge',
    DATE '2023-01-12',
    TRUE,
    'FW-3.1.0',
    DATE '2026-04-18',
    'MR-M3-001-status',
    'MR-M3-001-thresholds',
    1.5,
    1.9,
    2.4,
    3.0
),
(
    'MR-KND-001',
    'Katugastota Bridge Gauge',
    'ZONE-K1',
    7.3221,
    80.6255,
    'Katugastota-Kurunegala Road Bridge',
    DATE '2023-04-05',
    TRUE,
    'FW-3.1.0',
    DATE '2026-04-20',
    'MR-KND-001-status',
    'MR-KND-001-thresholds',
    2.0,
    2.7,
    3.3,
    4.0
),
(
    'MR-X1-001',
    'Getambe Basin Gauge',
    'ZONE-X1',
    7.2722,
    80.6046,
    'Getambe River Bank',
    DATE '2023-07-10',
    TRUE,
    'FW-3.1.0',
    DATE '2026-04-22',
    'MR-X1-001-status',
    'MR-X1-001-thresholds',
    2.4,
    3.0,
    3.7,
    4.5
),
(
    'MR-X1-002',
    'Peradeniya Gauge',
    'ZONE-X1',
    7.2642,
    80.5936,
    'Peradeniya Road Bridge',
    DATE '2023-06-03',
    TRUE,
    'FW-3.1.0',
    DATE '2026-03-28',
    'MR-X1-002-status',
    'MR-X1-002-thresholds',
    2.1,
    2.8,
    3.4,
    4.1
),
(
    'MR-T1-001',
    'Lower Delta Gauge',
    'ZONE-T1',
    8.4396,
    81.1835,
    'Mahaweli Main Branch, Inland Delta',
    DATE '2024-01-09',
    TRUE,
    'FW-3.1.0',
    DATE '2026-04-19',
    'MR-T1-001-status',
    'MR-T1-001-thresholds',
    1.7,
    2.3,
    2.9,
    3.4
);

INSERT INTO zone_shelters (
    shelter_id,
    zone_id,
    name,
    capacity,
    current_occupancy,
    lat,
    lng,
    distance_km,
    contact_number,
    status
)
VALUES
(
    'SHELTER-M3-01',
    'ZONE-M3',
    'Wickramabahu National School, Gampola',
    450,
    24,
    7.1585,
    80.5654,
    0.6,
    '+94-81-222-0001',
    'OPEN'
),
(
    'SHELTER-K1-01',
    'ZONE-K1',
    'Open University Polgolla Campus',
    800,
    68,
    7.3257,
    80.6521,
    0.9,
    '+94-81-222-1111',
    'OPEN'
),
(
    'SHELTER-X1-01',
    'ZONE-X1',
    'Peradeniya Central College',
    600,
    95,
    7.2682,
    80.5921,
    0.4,
    '+94-81-222-2222',
    'OPEN'
),
(
    'SHELTER-T1-01',
    'ZONE-T1',
    'Mutur Central College',
    550,
    36,
    8.4521,
    81.2658,
    1.4,
    '+94-81-222-3333',
    'OPEN'
);

INSERT INTO users (clerk_id, email, full_name, role, zone_id, is_active)
VALUES
('user_admin_mah', 'admin@floodsense.local', 'Mahaweli Admin', 'admin', NULL, TRUE),
('user_officer_k1', 'kandy.officer@floodsense.local', 'Kandy Field Officer', 'field_officer', 'ZONE-K1', TRUE),
('user_officer_x1', 'getambe.officer@floodsense.local', 'Getambe Field Officer', 'field_officer', 'ZONE-X1', TRUE),
('user_citizen_t1', 'citizen@floodsense.local', 'River Citizen', 'citizen', NULL, TRUE);

INSERT INTO model_metadata (version, accuracy, trained_at, deployed_at)
VALUES
(
    'v1.0',
    0.9142,
    TIMESTAMPTZ '2026-04-25 08:00:00+00',
    TIMESTAMPTZ '2026-04-26 08:30:00+00'
),
(
    'v1.1',
    0.9418,
    TIMESTAMPTZ '2026-05-02 08:00:00+00',
    TIMESTAMPTZ '2026-05-03 09:00:00+00'
);


INSERT INTO flood_predictions (zone_id, model_id, water_level)
VALUES
(
    'ZONE-M3',
    (SELECT model_id FROM model_metadata WHERE version = 'v1.1' LIMIT 1),
    '{"generated_at":"2026-05-13T00:00:00Z","horizons":[15,30,60],"records":[{"timestamp":"2026-05-12T23:00:00Z","y_pred_t_plus_15":1.7,"y_pred_t_plus_30":1.9,"y_pred_t_plus_60":2.1},{"timestamp":"2026-05-13T00:00:00Z","y_pred_t_plus_15":1.7,"y_pred_t_plus_30":1.9,"y_pred_t_plus_60":2.1}]}'::jsonb
),
(
    'ZONE-K1',
    (SELECT model_id FROM model_metadata WHERE version = 'v1.1' LIMIT 1),
    '{"generated_at":"2026-05-13T00:00:00Z","horizons":[15,30,60],"records":[{"timestamp":"2026-05-12T23:00:00Z","y_pred_t_plus_15":3.0,"y_pred_t_plus_30":3.4,"y_pred_t_plus_60":3.8},{"timestamp":"2026-05-13T00:00:00Z","y_pred_t_plus_15":3.0,"y_pred_t_plus_30":3.4,"y_pred_t_plus_60":3.8}]}'::jsonb
),
(
    'ZONE-X1',
    (SELECT model_id FROM model_metadata WHERE version = 'v1.1' LIMIT 1),
    '{"generated_at":"2026-05-13T00:00:00Z","horizons":[15,30,60],"records":[{"timestamp":"2026-05-12T23:00:00Z","y_pred_t_plus_15":4.4,"y_pred_t_plus_30":5.0,"y_pred_t_plus_60":5.5},{"timestamp":"2026-05-13T00:00:00Z","y_pred_t_plus_15":4.4,"y_pred_t_plus_30":5.0,"y_pred_t_plus_60":5.5}]}'::jsonb
),
(
    'ZONE-T1',
    (SELECT model_id FROM model_metadata WHERE version = 'v1.1' LIMIT 1),
    '{"generated_at":"2026-05-13T00:00:00Z","horizons":[15,30,60],"records":[{"timestamp":"2026-05-12T23:00:00Z","y_pred_t_plus_15":1.5,"y_pred_t_plus_30":1.7,"y_pred_t_plus_60":1.8},{"timestamp":"2026-05-13T00:00:00Z","y_pred_t_plus_15":1.5,"y_pred_t_plus_30":1.7,"y_pred_t_plus_60":1.8}]}'::jsonb
);

INSERT INTO alert_events (prediction_id, triggered_at)
SELECT prediction_id, TIMESTAMPTZ '2026-05-13 00:10:00+00'
FROM flood_predictions
WHERE zone_id IN ('ZONE-K1', 'ZONE-X1');
