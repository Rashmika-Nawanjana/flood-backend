from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import re
from typing import Any

import psycopg
from psycopg.rows import dict_row
from influxdb_client import InfluxDBClient

from app.core.config import settings


def _to_float(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def _to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_interval(interval: str) -> str:
    if re.match(r"^\d+[smhdw]$", interval):
        return interval
    return "1h"


def _get_pg_connection() -> psycopg.Connection:
    return psycopg.connect(settings.database_url, row_factory=dict_row)


def fetch_sensors() -> list[dict[str, Any]]:
    query = """
        SELECT
            s.sensor_id,
            s.name,
            s.zone_id,
            z.zone_name,
            s.lat,
            s.lng,
            s.address,
            s.installed_date,
            s.is_active,
            s.firmware_version,
            s.last_maintenance,
            s.list_status_key,
            s.list_thresholds_key,
            s.watch_m,
            s.advisory_m,
            s.warning_m,
            s.critical_m
        FROM sensor_nodes s
        LEFT JOIN zones z ON s.zone_id = z.zone_id
        WHERE s.is_active IS TRUE
        ORDER BY s.sensor_id
    """
    with _get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return list(cur.fetchall())


def fetch_sensors_by_zone(zone_id: str) -> list[dict[str, Any]]:
    query = """
        SELECT
            s.sensor_id,
            s.name,
            s.zone_id,
            z.zone_name,
            s.lat,
            s.lng,
            s.address,
            s.installed_date,
            s.is_active,
            s.firmware_version,
            s.last_maintenance,
            s.list_status_key,
            s.list_thresholds_key,
            s.watch_m,
            s.advisory_m,
            s.warning_m,
            s.critical_m
        FROM sensor_nodes s
        LEFT JOIN zones z ON s.zone_id = z.zone_id
        WHERE s.is_active IS TRUE AND s.zone_id = %s
        ORDER BY s.sensor_id
    """
    with _get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (zone_id,))
            return list(cur.fetchall())


def fetch_sensor(sensor_id: str) -> dict[str, Any] | None:
    query = """
        SELECT
            s.sensor_id,
            s.name,
            s.zone_id,
            z.zone_name,
            s.lat,
            s.lng,
            s.address,
            s.installed_date,
            s.is_active,
            s.firmware_version,
            s.last_maintenance,
            s.list_status_key,
            s.list_thresholds_key,
            s.watch_m,
            s.advisory_m,
            s.warning_m,
            s.critical_m
        FROM sensor_nodes s
        LEFT JOIN zones z ON s.zone_id = z.zone_id
        WHERE s.sensor_id = %s
        LIMIT 1
    """
    with _get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (sensor_id,))
            return cur.fetchone()


def fetch_zone(zone_id: str) -> dict[str, Any] | None:
    query = """
        SELECT
            z.zone_id,
            z.zone_name
        FROM zones z
        WHERE z.zone_id = %s
        LIMIT 1
    """
    with _get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (zone_id,))
            return cur.fetchone()


def _query_latest_measurement(
    sensor_id: str, measurement: str, fields: list[str]
) -> dict[str, Any]:
    if not settings.influxdb_token:
        return {}

    field_filter = " or ".join([f'r._field == "{field}"' for field in fields])
    flux = f"""
        from(bucket: "{settings.influxdb_bucket}")
          |> range(start: -7d)
          |> filter(fn: (r) => r._measurement == "{measurement}" and r.sensor_id == "{sensor_id}")
          |> filter(fn: (r) => {field_filter})
          |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> sort(columns: ["_time"], desc: true)
          |> limit(n: 1)
    """

    with InfluxDBClient(
        url=settings.influxdb_url,
        token=settings.influxdb_token,
        org=settings.influxdb_org,
    ) as client:
        tables = client.query_api().query(flux)

    if not tables:
        return {}

    record = tables[0].records[0]
    values = record.values
    payload: dict[str, Any] = {field: values.get(field) for field in fields}
    payload["timestamp"] = record.get_time()
    return payload


def get_latest_reading(sensor_id: str) -> dict[str, Any]:
    return _query_latest_measurement(
        sensor_id,
        "sensor_readings",
        [
            "water_level_m",
            "rainfall_mm_per_hr",
            "flow_velocity_mps",
            "temperature_c",
            "air_pressure_hpa",
        ],
    )


def get_latest_status(sensor_id: str) -> dict[str, Any]:
    payload = _query_latest_measurement(
        sensor_id,
        "sensor_status",
        ["battery_percent", "signal_strength_dbm"],
    )
    if not payload:
        return {}
    return {
        "battery_percent": payload.get("battery_percent"),
        "signal_strength_dbm": payload.get("signal_strength_dbm"),
        "last_seen": payload.get("timestamp"),
    }


def get_history(
    sensor_id: str, start: datetime, stop: datetime, interval: str
) -> list[dict[str, Any]]:
    if not settings.influxdb_token:
        return []

    interval = _validate_interval(interval)
    start_iso = _to_iso(start)
    stop_iso = _to_iso(stop)
    flux = f"""
        from(bucket: "{settings.influxdb_bucket}")
          |> range(start: time(v: "{start_iso}"), stop: time(v: "{stop_iso}"))
          |> filter(fn: (r) => r._measurement == "sensor_readings" and r.sensor_id == "{sensor_id}")
          |> filter(fn: (r) =>
              r._field == "water_level_m" or
              r._field == "rainfall_mm_per_hr" or
              r._field == "flow_velocity_mps" or
              r._field == "temperature_c" or
              r._field == "air_pressure_hpa"
          )
          |> aggregateWindow(every: {interval}, fn: mean, createEmpty: false)
          |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> sort(columns: ["_time"])
    """

    with InfluxDBClient(
        url=settings.influxdb_url,
        token=settings.influxdb_token,
        org=settings.influxdb_org,
    ) as client:
        tables = client.query_api().query(flux)

    records = []
    for table in tables:
        records.extend(table.records)

    data: list[dict[str, Any]] = []
    for record in records:
        values = record.values
        timestamp = record.get_time()
        data.append(
            {
                "timestamp": _to_iso(timestamp),
                "water_level_m": _to_float(values.get("water_level_m")),
                "rainfall_mm": _to_float(values.get("rainfall_mm_per_hr")),
                "flow_velocity_mps": _to_float(values.get("flow_velocity_mps")),
                "temperature_c": _to_float(values.get("temperature_c")),
                "air_pressure_hpa": _to_float(values.get("air_pressure_hpa")),
            }
        )

    return data
