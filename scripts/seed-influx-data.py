#!/usr/bin/env python
"""Seed sample InfluxDB readings for /v1/sensors and /v1/anomalies docs testing."""

from __future__ import annotations

import time
import os
from pathlib import Path

from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from dotenv import load_dotenv


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value:
        return value
    return default


def _build_lines(now_ns: int, hours: int = 24) -> str:
    readings = [
        (
            "MR-KND-001",
            {
                "water_level_m": 4.53,
                "rainfall_mm_per_hr": 8.2,
                "flow_velocity_mps": 0.85,
                "temperature_c": 28.5,
                "air_pressure_hpa": 1011.2,
            },
            {
                "battery_percent": 75,
                "signal_strength_dbm": -68,
            },
        ),
        (
            "MR-KND-002",
            {
                "water_level_m": 2.1,
                "rainfall_mm_per_hr": 0.0,
                "flow_velocity_mps": 0.42,
                "temperature_c": 27.8,
                "air_pressure_hpa": 1012.5,
            },
            {
                "battery_percent": 92,
                "signal_strength_dbm": -55,
            },
        ),
    ]

    lines: list[str] = []
    for hour_offset in range(hours, -1, -1):
        ts_ns = now_ns - (hour_offset * 3600 * 1_000_000_000)
        for sensor_id, reading, status in readings:
            reading_fields = ",".join(
                [f"{k}={v}" for k, v in reading.items()]
            )
            lines.append(
                f"sensor_readings,sensor_id={sensor_id} {reading_fields} {ts_ns}"
            )

            if hour_offset == 0:
                status_fields = (
                    f"battery_percent={status['battery_percent']}i,"
                    f"signal_strength_dbm={status['signal_strength_dbm']}i"
                )
                lines.append(
                    f"sensor_status,sensor_id={sensor_id} {status_fields} {ts_ns}"
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

    write_url = (
        f"{influx_url.rstrip('/')}/api/v2/write?org={org}&bucket={bucket}&precision=ns"
    )

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
    return 0


if __name__ == "__main__":
    raise SystemExit(seed())
