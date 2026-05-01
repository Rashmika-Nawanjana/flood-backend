from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
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


def _ensure_dict(value: Any) -> dict | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def _get_pg_connection() -> psycopg.Connection:
    return psycopg.connect(settings.database_url, row_factory=dict_row)


def fetch_zones() -> list[dict[str, Any]]:
    query = """
        SELECT
            z.zone_id,
            z.zone_name,
            z.description,
            z.risk_level,
            z.risk_score,
            z.color_code,
            z.population_at_risk,
            z.active_alerts,
            z.last_updated,
            z.geometry,
            z.current_conditions,
            z.prediction,
            COALESCE(
                ARRAY_AGG(s.sensor_id ORDER BY s.sensor_id)
                FILTER (WHERE s.sensor_id IS NOT NULL),
                ARRAY[]::varchar[]
            ) AS sensors_in_zone
        FROM zones z
        LEFT JOIN sensor_nodes s ON s.zone_id = z.zone_id AND s.is_active IS TRUE
        GROUP BY z.zone_id
        ORDER BY z.zone_id
    """
    with _get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return list(cur.fetchall())


def fetch_zone(zone_id: str) -> dict[str, Any] | None:
    query = """
        SELECT
            z.zone_id,
            z.zone_name,
            z.description,
            z.risk_level,
            z.risk_score,
            z.color_code,
            z.population_at_risk,
            z.active_alerts,
            z.last_updated,
            z.geometry,
            z.current_conditions,
            z.prediction
        FROM zones z
        WHERE z.zone_id = %s
        LIMIT 1
    """
    with _get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (zone_id,))
            return cur.fetchone()


def fetch_zone_shelters(zone_id: str) -> list[dict[str, Any]]:
    query = """
        SELECT
            shelter_id,
            name,
            capacity,
            current_occupancy,
            lat,
            lng,
            distance_km,
            contact_number,
            status
        FROM zone_shelters
        WHERE zone_id = %s
        ORDER BY shelter_id
    """
    with _get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (zone_id,))
            return list(cur.fetchall())


def get_zone_conditions(zone_id: str) -> dict[str, Any]:
    if not settings.influxdb_token:
        return {}

    fields = [
        "avg_water_level_m",
        "max_water_level_m",
        "avg_flow_velocity_mps",
        "total_rainfall_mm",
        "trend",
    ]
    field_filter = " or ".join([f'r._field == "{field}"' for field in fields])
    flux = f"""
        from(bucket: "{settings.influxdb_bucket}")
          |> range(start: -7d)
          |> filter(fn: (r) => r._measurement == "zone_conditions" and r.zone_id == "{zone_id}")
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
    return {
        "avg_water_level_m": _to_float(values.get("avg_water_level_m")),
        "max_water_level_m": _to_float(values.get("max_water_level_m")),
        "avg_flow_velocity_mps": _to_float(values.get("avg_flow_velocity_mps")),
        "total_rainfall_mm": _to_float(values.get("total_rainfall_mm")),
        "trend": values.get("trend"),
        "timestamp": record.get_time(),
    }


def normalize_zone_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "zone_id": row.get("zone_id"),
        "zone_name": row.get("zone_name"),
        "description": row.get("description"),
        "risk_level": row.get("risk_level"),
        "risk_score": _to_float(row.get("risk_score")),
        "color_code": row.get("color_code"),
        "population_at_risk": row.get("population_at_risk"),
        "active_alerts": row.get("active_alerts"),
        "last_updated": _to_iso(row.get("last_updated"))
        if row.get("last_updated")
        else None,
        "geometry": _ensure_dict(row.get("geometry")),
        "current_conditions": _ensure_dict(row.get("current_conditions")),
        "prediction": _ensure_dict(row.get("prediction")),
        "sensors_in_zone": row.get("sensors_in_zone", []),
    }
