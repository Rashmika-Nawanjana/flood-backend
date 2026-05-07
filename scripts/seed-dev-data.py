#!/usr/bin/env python
"""Seed minimal zone + sensor data for local /docs testing."""

from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import date

import psycopg
from dotenv import load_dotenv


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


def _apply_schema(conn: psycopg.Connection) -> None:
    sql_path = Path(__file__).parent.parent / "migrations" / "sql" / "0002_zone_model.sql"
    if not sql_path.exists():
        print(f"WARN: Schema file not found: {sql_path}")
        return

    conn.execute(sql_path.read_text(encoding="utf-8"))


def seed() -> int:
    db_url = _get_database_url()
    zone_id = "ZONE-K1"

    geometry = {
        "type": "Polygon",
        "coordinates": [
            [
                [80.6300, 7.2880],
                [80.6380, 7.2880],
                [80.6380, 7.2950],
                [80.6300, 7.2950],
                [80.6300, 7.2880],
            ]
        ],
    }
    current_conditions = {
        "avg_water_level_m": 2.1,
        "max_water_level_m": 3.4,
        "avg_flow_velocity_mps": 1.8,
        "total_rainfall_mm": 18.2,
        "trend": "RISING",
    }
    prediction = {
        "flood_probability_percent": 28.5,
        "predicted_peak_level_m": 3.7,
        "estimated_flood_time": "2026-05-06T18:30:00Z",
        "confidence_percent": 72.0,
        "model_version": "v1.0",
    }

    zone_payload = (
        zone_id,
        "Kandy Central",
        "Seed zone for docs testing",
        "MEDIUM",
        0.42,
        "#4DA3FF",
        12000,
        1,
        json.dumps(geometry),
        json.dumps(current_conditions),
        json.dumps(prediction),
    )

    sensors = [
        (
            "MR-KND-001",
            "Kandy River Gauge",
            zone_id,
            7.2906,
            80.6337,
            "Kandy Lake Road",
            date(2024, 5, 12),
            True,
            "FW-2.3.1",
            date(2026, 4, 10),
            2.5,
            3.2,
        ),
        (
            "MR-KND-002",
            "Peradeniya Gauge",
            zone_id,
            7.2730,
            80.5954,
            "Peradeniya Road",
            date(2024, 6, 3),
            True,
            "FW-2.3.1",
            date(2026, 3, 22),
            2.2,
            2.9,
        ),
    ]

    shelters = [
        (
            "SHELTER-KND-01",
            zone_id,
            "Kandy City Hall",
            250,
            45,
            7.2915,
            80.6365,
            0.9,
            "+94-81-222-1111",
            "OPEN",
        ),
        (
            "SHELTER-KND-02",
            zone_id,
            "Peradeniya Community Center",
            300,
            120,
            7.2712,
            80.5959,
            4.2,
            "+94-81-222-2222",
            "OPEN",
        ),
    ]

    zone_sql = """
        INSERT INTO zones (
            zone_id,
            zone_name,
            description,
            risk_level,
            risk_score,
            color_code,
            population_at_risk,
            active_alerts,
            geometry,
            current_conditions,
            prediction,
            last_updated
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, NOW())
        ON CONFLICT (zone_id)
        DO UPDATE SET
            zone_name = EXCLUDED.zone_name,
            description = EXCLUDED.description,
            risk_level = EXCLUDED.risk_level,
            risk_score = EXCLUDED.risk_score,
            color_code = EXCLUDED.color_code,
            population_at_risk = EXCLUDED.population_at_risk,
            active_alerts = EXCLUDED.active_alerts,
            geometry = EXCLUDED.geometry,
            current_conditions = EXCLUDED.current_conditions,
            prediction = EXCLUDED.prediction,
            last_updated = NOW();
    """

    sensor_sql = """
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
            warning_m,
            critical_m
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (sensor_id)
        DO UPDATE SET
            name = EXCLUDED.name,
            zone_id = EXCLUDED.zone_id,
            lat = EXCLUDED.lat,
            lng = EXCLUDED.lng,
            address = EXCLUDED.address,
            installed_date = EXCLUDED.installed_date,
            is_active = EXCLUDED.is_active,
            firmware_version = EXCLUDED.firmware_version,
            last_maintenance = EXCLUDED.last_maintenance,
            warning_m = EXCLUDED.warning_m,
            critical_m = EXCLUDED.critical_m;
    """

    shelter_sql = """
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
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (shelter_id)
        DO UPDATE SET
            zone_id = EXCLUDED.zone_id,
            name = EXCLUDED.name,
            capacity = EXCLUDED.capacity,
            current_occupancy = EXCLUDED.current_occupancy,
            lat = EXCLUDED.lat,
            lng = EXCLUDED.lng,
            distance_km = EXCLUDED.distance_km,
            contact_number = EXCLUDED.contact_number,
            status = EXCLUDED.status;
    """

    try:
        with psycopg.connect(db_url) as conn:
            _apply_schema(conn)
            with conn.cursor() as cur:
                cur.execute(zone_sql, zone_payload)
                cur.executemany(sensor_sql, sensors)
                cur.executemany(shelter_sql, shelters)
        print("OK: Seed data inserted")
        print(f"   Zone: {zone_id}")
        print("   Sensors: MR-KND-001, MR-KND-002")
        print("   Shelters: SHELTER-KND-01, SHELTER-KND-02")
        return 0
    except Exception as exc:
        print(f"ERROR: Seeding failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(seed())
