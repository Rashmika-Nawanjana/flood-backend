#!/usr/bin/env python
"""Reset and seed a coherent Mahaweli-based dev dataset for Postgres.

The seed order is:
1. rivers
2. zones with prev/next links
3. sensor_nodes and zone_shelters
4. users
5. model_metadata
6. anomalies
7. flood_predictions
8. alert_events

Legacy tables are truncated too when they exist, so the script can be rerun
cleanly during local development.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv


LEGACY_TABLES = [
    "alert_events",
    "anomalies",
    "flood_predictions",
    "sensor_nodes",
    "zone_shelters",
    "zones",
    "users",
    "model_metadata",
    "rivers",
    "station",
    "sensors",
    "shelters",
    "evacuation_routes",
    "historical_floods",
]


@dataclass(frozen=True)
class ZoneSeed:
    zone_id: str
    zone_name: str
    description: str
    risk_level: str
    risk_score: float
    color_code: str
    population_at_risk: int
    active_alerts: int
    geometry: dict[str, Any]
    current_conditions: dict[str, Any]
    prediction: dict[str, Any]
    prev_zone_id: str | None
    next_zone_id: str | None


def _get_database_url() -> str:
    load_dotenv(Path(__file__).parent.parent / ".env")
    url = os.getenv("DATABASE_URL")
    if url:
        return url.replace("postgresql+psycopg://", "postgresql://")

    user = os.getenv("POSTGRES_USER", "admin")
    password = os.getenv("POSTGRES_PASSWORD", "admin")
    database = os.getenv("POSTGRES_DB", "flooddb")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def _table_exists(conn: psycopg.Connection, table_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s)", (table_name,))
        row = cur.fetchone()
    return bool(row and row[0])


def _truncate_seed_tables(conn: psycopg.Connection) -> None:
    existing = [name for name in LEGACY_TABLES if _table_exists(conn, name)]
    if not existing:
        return
    quoted = ", ".join(f'"{name}"' for name in existing)
    conn.execute(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE")


def _ts(minutes_offset: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes_offset)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _water_level_payload(base_ts: str, horizons: list[int], values: list[float]) -> dict[str, Any]:
    record = {"timestamp": base_ts}
    for horizon, value in zip(horizons, values, strict=True):
        record[f"y_pred_t_plus_{horizon}"] = value
    return {
        "generated_at": _ts(),
        "horizons": horizons,
        "records": [
            {"timestamp": _ts(-60), **record},
            {"timestamp": base_ts, **record},
        ],
    }


def seed() -> int:
    db_url = _get_database_url()

    river_name = "Mahaweli River"
    zones = [
        ZoneSeed(
            zone_id="ZONE-M3",
            zone_name="Mahaweli Upper Catchment",
            description="Upper basin around the Kandy hills",
            risk_level="MEDIUM",
            risk_score=0.34,
            color_code="#4DA3FF",
            population_at_risk=5400,
            active_alerts=0,
            geometry={"type": "Point", "coordinates": [80.615, 7.865]},
            current_conditions={"avg_water_level_m": 1.3, "flow_velocity_mps": 1.0, "trend": "RISING"},
            prediction={"predicted_peak_level_m": 2.0, "flood_probability_percent": 18.0},
            prev_zone_id=None,
            next_zone_id="ZONE-K1",
        ),
        ZoneSeed(
            zone_id="ZONE-K1",
            zone_name="Kandy Central",
            description="Urban Kandy reach of the Mahaweli",
            risk_level="HIGH",
            risk_score=0.78,
            color_code="#FF6B6B",
            population_at_risk=12800,
            active_alerts=2,
            geometry={"type": "Polygon", "coordinates": [[[80.628, 7.286], [80.640, 7.286], [80.640, 7.296], [80.628, 7.296], [80.628, 7.286]]]},
            current_conditions={"avg_water_level_m": 2.2, "max_water_level_m": 3.6, "trend": "RISING"},
            prediction={"predicted_peak_level_m": 4.4, "flood_probability_percent": 61.0},
            prev_zone_id="ZONE-M3",
            next_zone_id="ZONE-X1",
        ),
        ZoneSeed(
            zone_id="ZONE-X1",
            zone_name="Getambe Basin",
            description="Confluence and midstream zone downstream of Kandy",
            risk_level="HIGH",
            risk_score=0.86,
            color_code="#F97316",
            population_at_risk=14600,
            active_alerts=3,
            geometry={"type": "Polygon", "coordinates": [[[80.600, 7.250], [80.615, 7.250], [80.615, 7.265], [80.600, 7.265], [80.600, 7.250]]]},
            current_conditions={"avg_water_level_m": 2.9, "max_water_level_m": 4.8, "trend": "RISING"},
            prediction={"predicted_peak_level_m": 5.2, "flood_probability_percent": 84.0},
            prev_zone_id="ZONE-K1",
            next_zone_id="ZONE-T1",
        ),
        ZoneSeed(
            zone_id="ZONE-T1",
            zone_name="Mahaweli Lower Delta",
            description="Lower floodplain approaching the river mouth",
            risk_level="MEDIUM",
            risk_score=0.56,
            color_code="#FFD166",
            population_at_risk=8700,
            active_alerts=1,
            geometry={"type": "Point", "coordinates": [80.965, 7.112]},
            current_conditions={"avg_water_level_m": 1.8, "flow_velocity_mps": 0.7, "trend": "STABLE"},
            prediction={"predicted_peak_level_m": 2.7, "flood_probability_percent": 34.0},
            prev_zone_id="ZONE-X1",
            next_zone_id=None,
        ),
    ]

    sensors = [
        {"sensor_id": "MR-M3-001", "name": "Upper Catchment Gauge", "zone_id": "ZONE-M3", "lat": 7.8652, "lng": 80.6164, "address": "Upper Mahaweli Rd", "installed_date": date(2023, 1, 12), "firmware_version": "FW-3.1.0", "last_maintenance": date(2026, 4, 18), "watch_m": 1.5, "advisory_m": 1.9, "warning_m": 2.4, "critical_m": 3.0},
        {"sensor_id": "MR-KND-001", "name": "Kandy Bridge Gauge", "zone_id": "ZONE-K1", "lat": 7.2906, "lng": 80.6337, "address": "Kandy Lake Road", "installed_date": date(2023, 4, 5), "firmware_version": "FW-3.1.0", "last_maintenance": date(2026, 4, 20), "watch_m": 2.0, "advisory_m": 2.7, "warning_m": 3.3, "critical_m": 4.0},
        {"sensor_id": "MR-KND-002", "name": "Peradeniya Gauge", "zone_id": "ZONE-K1", "lat": 7.2730, "lng": 80.5954, "address": "Peradeniya Road", "installed_date": date(2023, 6, 3), "firmware_version": "FW-3.1.0", "last_maintenance": date(2026, 3, 28), "watch_m": 2.1, "advisory_m": 2.8, "warning_m": 3.4, "critical_m": 4.1},
        {"sensor_id": "MR-X1-001", "name": "Getambe Basin Gauge", "zone_id": "ZONE-X1", "lat": 7.2425, "lng": 80.6170, "address": "Getambe Main Rd", "installed_date": date(2023, 7, 10), "firmware_version": "FW-3.1.0", "last_maintenance": date(2026, 4, 22), "watch_m": 2.4, "advisory_m": 3.0, "warning_m": 3.7, "critical_m": 4.5},
        {"sensor_id": "MR-X1-002", "name": "Getambe Tributary Gauge", "zone_id": "ZONE-X1", "lat": 7.2511, "lng": 80.6032, "address": "Tributary Access Road", "installed_date": date(2024, 2, 14), "firmware_version": "FW-3.1.0", "last_maintenance": date(2026, 4, 25), "watch_m": 2.3, "advisory_m": 3.1, "warning_m": 3.8, "critical_m": 4.6},
        {"sensor_id": "MR-T1-001", "name": "Lower Delta Gauge", "zone_id": "ZONE-T1", "lat": 7.1124, "lng": 80.9654, "address": "Delta Floodplain Road", "installed_date": date(2024, 1, 9), "firmware_version": "FW-3.1.0", "last_maintenance": date(2026, 4, 19), "watch_m": 1.7, "advisory_m": 2.3, "warning_m": 2.9, "critical_m": 3.4},
    ]

    shelters = [
        {"shelter_id": "SHELTER-M3-01", "zone_id": "ZONE-M3", "name": "Halloluwa Community Centre", "capacity": 180, "current_occupancy": 24, "lat": 7.8721, "lng": 80.6194, "distance_km": 1.2, "contact_number": "+94-81-222-0001", "status": "OPEN"},
        {"shelter_id": "SHELTER-K1-01", "zone_id": "ZONE-K1", "name": "Kandy City Hall", "capacity": 260, "current_occupancy": 68, "lat": 7.2921, "lng": 80.6350, "distance_km": 0.8, "contact_number": "+94-81-222-1111", "status": "OPEN"},
        {"shelter_id": "SHELTER-X1-01", "zone_id": "ZONE-X1", "name": "Getambe Public Hall", "capacity": 320, "current_occupancy": 95, "lat": 7.2450, "lng": 80.6158, "distance_km": 0.9, "contact_number": "+94-81-222-2222", "status": "OPEN"},
        {"shelter_id": "SHELTER-T1-01", "zone_id": "ZONE-T1", "name": "Lower Delta School", "capacity": 210, "current_occupancy": 36, "lat": 7.1138, "lng": 80.9632, "distance_km": 1.4, "contact_number": "+94-81-222-3333", "status": "OPEN"},
    ]

    users = [
        {"clerk_id": "user_admin_mah", "email": "admin@floodsense.local", "full_name": "Mahaweli Admin", "role": "admin", "zone_id": None},
        {"clerk_id": "user_officer_k1", "email": "kandy.officer@floodsense.local", "full_name": "Kandy Field Officer", "role": "field_officer", "zone_id": "ZONE-K1"},
        {"clerk_id": "user_officer_x1", "email": "getambe.officer@floodsense.local", "full_name": "Getambe Field Officer", "role": "field_officer", "zone_id": "ZONE-X1"},
        {"clerk_id": "user_citizen_t1", "email": "citizen@floodsense.local", "full_name": "River Citizen", "role": "citizen", "zone_id": None},
    ]

    model_rows = [
        {"version": "v1.0", "accuracy": 0.9142, "trained_at": datetime(2026, 4, 25, 8, 0, tzinfo=timezone.utc), "deployed_at": datetime(2026, 4, 26, 8, 30, tzinfo=timezone.utc)},
        {"version": "v1.1", "accuracy": 0.9418, "trained_at": datetime(2026, 5, 2, 8, 0, tzinfo=timezone.utc), "deployed_at": datetime(2026, 5, 3, 9, 0, tzinfo=timezone.utc)},
    ]

    anomaly_rows = [
        {
            "anomaly_id": "ANOM-K1-001",
            "sensor_id": "MR-KND-001",
            "zone_id": "ZONE-K1",
            "detected_at": datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc),
            "type": "Rapid water rise",
            "severity": "HIGH",
            "anomaly_score": 0.8421,
            "reading": {"water_level_m": 3.95, "rainfall_mm_per_hr": 12.4, "flow_velocity_mps": 0.91},
            "status": "UNRESOLVED",
        },
        {
            "anomaly_id": "ANOM-X1-001",
            "sensor_id": "MR-X1-001",
            "zone_id": "ZONE-X1",
            "detected_at": datetime(2026, 5, 7, 9, 20, tzinfo=timezone.utc),
            "type": "Threshold breach",
            "severity": "CRITICAL",
            "anomaly_score": 0.9314,
            "reading": {"water_level_m": 4.92, "rainfall_mm_per_hr": 15.8, "flow_velocity_mps": 1.03},
            "status": "UNRESOLVED",
        },
    ]

    prediction_rows = [
        {
            "zone_id": "ZONE-M3",
            "horizons": [15, 30, 60],
            "values": [1.7, 1.9, 2.1],
        },
        {
            "zone_id": "ZONE-K1",
            "horizons": [15, 30, 60],
            "values": [3.6, 4.2, 4.7],
        },
        {
            "zone_id": "ZONE-X1",
            "horizons": [15, 30, 60],
            "values": [4.4, 5.0, 5.5],
        },
        {
            "zone_id": "ZONE-T1",
            "horizons": [15, 30, 60],
            "values": [2.1, 2.4, 2.8],
        },
    ]

    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                _truncate_seed_tables(conn)

                cur.execute("INSERT INTO rivers (river_name) VALUES (%s) RETURNING river_id", (river_name,))
                river_id = cur.fetchone()[0]

                zone_insert = """
                    INSERT INTO zones (
                        zone_id, zone_name, description, risk_level, risk_score,
                        color_code, population_at_risk, active_alerts, river_id,
                        prev_zone_id, next_zone_id, geometry, current_conditions,
                        prediction, last_updated
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, NOW())
                """
                for zone in zones:
                    cur.execute(
                        zone_insert,
                        (
                            zone.zone_id,
                            zone.zone_name,
                            zone.description,
                            zone.risk_level,
                            zone.risk_score,
                            zone.color_code,
                            zone.population_at_risk,
                            zone.active_alerts,
                            river_id,
                            None,
                            None,
                            json.dumps(zone.geometry),
                            json.dumps(zone.current_conditions),
                            json.dumps(zone.prediction),
                        ),
                    )

                zone_links = {
                    zone.zone_id: (zone.prev_zone_id, zone.next_zone_id)
                    for zone in zones
                }
                for zone_id, (prev_zone_id, next_zone_id) in zone_links.items():
                    cur.execute(
                        """
                        UPDATE zones
                        SET prev_zone_id = %s,
                            next_zone_id = %s
                        WHERE zone_id = %s
                        """,
                        (prev_zone_id, next_zone_id, zone_id),
                    )

                sensor_insert = """
                    INSERT INTO sensor_nodes (
                        sensor_id, name, zone_id, lat, lng, address,
                        installed_date, is_active, firmware_version, last_maintenance,
                        list_status_key, list_thresholds_key, watch_m, advisory_m,
                        warning_m, critical_m
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                for sensor in sensors:
                    cur.execute(
                        sensor_insert,
                        (
                            sensor["sensor_id"],
                            sensor["name"],
                            sensor["zone_id"],
                            sensor["lat"],
                            sensor["lng"],
                            sensor["address"],
                            sensor["installed_date"],
                            True,
                            sensor["firmware_version"],
                            sensor["last_maintenance"],
                            f"{sensor['sensor_id']}-status",
                            f"{sensor['sensor_id']}-thresholds",
                            sensor["watch_m"],
                            sensor["advisory_m"],
                            sensor["warning_m"],
                            sensor["critical_m"],
                        ),
                    )

                shelter_insert = """
                    INSERT INTO zone_shelters (
                        shelter_id, zone_id, name, capacity, current_occupancy,
                        lat, lng, distance_km, contact_number, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                for shelter in shelters:
                    cur.execute(
                        shelter_insert,
                        (
                            shelter["shelter_id"],
                            shelter["zone_id"],
                            shelter["name"],
                            shelter["capacity"],
                            shelter["current_occupancy"],
                            shelter["lat"],
                            shelter["lng"],
                            shelter["distance_km"],
                            shelter["contact_number"],
                            shelter["status"],
                        ),
                    )

                user_insert = """
                    INSERT INTO users (clerk_id, email, full_name, role, zone_id, is_active)
                    VALUES (%s, %s, %s, %s, %s, TRUE)
                """
                for user in users:
                    cur.execute(
                        user_insert,
                        (
                            user["clerk_id"],
                            user["email"],
                            user["full_name"],
                            user["role"],
                            user["zone_id"],
                        ),
                    )

                model_id_by_version: dict[str, int] = {}
                for model in model_rows:
                    cur.execute(
                        """
                        INSERT INTO model_metadata (version, accuracy, trained_at, deployed_at)
                        VALUES (%s, %s, %s, %s)
                        RETURNING model_id
                        """,
                        (model["version"], model["accuracy"], model["trained_at"], model["deployed_at"]),
                    )
                    model_id_by_version[model["version"]] = int(cur.fetchone()[0])

                latest_model_id = model_id_by_version["v1.1"]

                prediction_id_by_zone: dict[str, int] = {}
                prediction_insert = """
                    INSERT INTO flood_predictions (zone_id, model_id, water_level)
                    VALUES (%s, %s, %s)
                    RETURNING prediction_id
                """
                for idx, item in enumerate(prediction_rows):
                    base_ts = _ts(idx * 5)
                    water_level = _water_level_payload(base_ts, item["horizons"], item["values"])
                    cur.execute(prediction_insert, (item["zone_id"], latest_model_id, json.dumps(water_level)))
                    prediction_id_by_zone[item["zone_id"]] = int(cur.fetchone()[0])

                alert_insert = """
                    INSERT INTO alert_events (prediction_id, triggered_at)
                    VALUES (%s, %s)
                """
                for zone_id in ("ZONE-K1", "ZONE-X1"):
                    cur.execute(alert_insert, (prediction_id_by_zone[zone_id], datetime.now(timezone.utc)))

                anomaly_insert = """
                    INSERT INTO anomalies (
                        anomaly_id, sensor_id, zone_id, detected_at, type, severity,
                        anomaly_score, reading, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                for anomaly in anomaly_rows:
                    cur.execute(
                        anomaly_insert,
                        (
                            anomaly["anomaly_id"],
                            anomaly["sensor_id"],
                            anomaly["zone_id"],
                            anomaly["detected_at"],
                            anomaly["type"],
                            anomaly["severity"],
                            anomaly["anomaly_score"],
                            json.dumps(anomaly["reading"]),
                            anomaly["status"],
                        ),
                    )

            conn.commit()

        print("OK: Mahaweli seed data inserted cleanly")
        print("   River: Mahaweli River")
        print("   Zones: ZONE-M3 -> ZONE-K1 -> ZONE-X1 -> ZONE-T1")
        print("   Sensors: 6")
        print("   Shelters: 4")
        print("   Users: 4")
        print("   Models: 2")
        print("   Predictions: 4")
        print("   Alerts: 2")
        print("   Anomalies: 2")
        return 0
    except Exception as exc:
        print(f"ERROR: Seeding failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(seed())
