#!/usr/bin/env python3
"""Seed coherent Mahaweli telemetry into InfluxDB for sensor/anomaly testing."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


SENSOR_SERIES = [
    {
        "sensor_id": "MR-M3-001",
        "water_level_m": 1.35,
        "rainfall_mm_per_hr": 1.4,
        "flow_velocity_mps": 0.95,
        "temperature_c": 26.8,
        "air_pressure_hpa": 1014.0,
        "battery_percent": 88,
        "signal_strength_dbm": -58,
        "trend": 0.01,
    },
    {
        "sensor_id": "MR-KND-001",
        "water_level_m": 2.25,
        "rainfall_mm_per_hr": 6.5,
        "flow_velocity_mps": 1.10,
        "temperature_c": 27.6,
        "air_pressure_hpa": 1012.8,
        "battery_percent": 81,
        "signal_strength_dbm": -63,
        "trend": 0.03,
    },
    {
        "sensor_id": "MR-X1-001",
        "water_level_m": 4.35,
        "rainfall_mm_per_hr": 11.2,
        "flow_velocity_mps": 1.32,
        "temperature_c": 28.1,
        "air_pressure_hpa": 1010.9,
        "battery_percent": 74,
        "signal_strength_dbm": -69,
        "trend": 0.05,
    },
    {
        "sensor_id": "MR-T1-001",
        "water_level_m": 2.05,
        "rainfall_mm_per_hr": 3.1,
        "flow_velocity_mps": 0.82,
        "temperature_c": 27.0,
        "air_pressure_hpa": 1013.1,
        "battery_percent": 90,
        "signal_strength_dbm": -56,
        "trend": 0.02,
    },
]


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value:
        return value
    return default


def _build_lines(now_ns: int, hours: int = 36) -> str:
    lines: list[str] = []
    for hour_offset in range(hours, -1, -1):
        ts_ns = now_ns - (hour_offset * 3600 * 1_000_000_000)
        time_factor = (hours - hour_offset) / max(hours, 1)

        for sensor in SENSOR_SERIES:
            level = round(sensor["water_level_m"] + (sensor["trend"] * time_factor * 1.2), 3)
            rainfall = round(max(0.0, sensor["rainfall_mm_per_hr"] + (time_factor * 2.0) - 0.8), 2)
            flow_velocity = round(sensor["flow_velocity_mps"] + (sensor["trend"] * 0.35), 3)
            temperature = round(sensor["temperature_c"] + ((time_factor - 0.5) * 0.6), 2)
            pressure = round(sensor["air_pressure_hpa"] - (time_factor * 0.9), 2)

            reading_fields = (
                f"water_level_m={level},"
                f"rainfall_mm_per_hr={rainfall},"
                f"flow_velocity_mps={flow_velocity},"
                f"temperature_c={temperature},"
                f"air_pressure_hpa={pressure}"
            )
            lines.append(
                f"sensor_readings,sensor_id={sensor['sensor_id']} {reading_fields} {ts_ns}"
            )

            if hour_offset in (0, 1):
                status_fields = (
                    f"battery_percent={sensor['battery_percent']}i,"
                    f"signal_strength_dbm={sensor['signal_strength_dbm']}i"
                )
                lines.append(
                    f"sensor_status,sensor_id={sensor['sensor_id']} {status_fields} {ts_ns}"
                )

    return "\n".join(lines)


def seed() -> int:
    load_dotenv(Path(__file__).parent.parent / ".env")

    influx_url = _get_env("INFLUXDB_URL", "http://localhost:8086")
    token = _get_env("INFLUXDB_TOKEN")
    org = _get_env("INFLUXDB_ORG", "flood")
    bucket = _get_env("INFLUXDB_BUCKET", "telemetry")

    if not token:
        print("ERROR: INFLUXDB_TOKEN is not set")
        return 1

    write_url = f"{influx_url.rstrip('/')}/api/v2/write?org={org}&bucket={bucket}&precision=ns"

    now_ns = time.time_ns()
    lines = _build_lines(now_ns)
    payload = lines.encode("utf-8")

    request = Request(
        write_url,
        data=payload,
        headers={
            "Authorization": f"Token {token}",
            "Content-Type": "text/plain; charset=utf-8",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            if response.status >= 300:
                body = response.read().decode("utf-8", errors="replace").strip()
                print(f"ERROR: Influx write failed ({response.status})")
                if body:
                    print(body)
                return 1
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace").strip()
        print(f"ERROR: Influx write failed ({exc.code})")
        if body:
            print(body)
        return 1
    except URLError as exc:
        print(f"ERROR: Influx connection failed: {exc}")
        return 1

    print("OK: Influx seed data inserted")
    print(f"   Sensors: {', '.join(sensor['sensor_id'] for sensor in SENSOR_SERIES)}")
    print(f"   Window: 36 hours ending at {datetime.now(timezone.utc).isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(seed())
