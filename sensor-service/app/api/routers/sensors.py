from datetime import datetime, timedelta, timezone
from decimal import Decimal
import re

from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.services.sensor_data import (
    fetch_sensors_by_zone,
    fetch_sensor,
    fetch_sensors,
    fetch_zone,
    fetch_anomalies,
    fetch_zone_anomalies,
    get_history,
    get_latest_reading,
    get_latest_status,
)

router = APIRouter(prefix="/v1", tags=["sensors"])


def _to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_float(value):
    if isinstance(value, Decimal):
        return float(value)
    return value


def _date_to_str(value) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _normalize_interval(interval: str) -> str:
    if re.match(r"^\d+[smhdw]$", interval):
        return interval
    return "1h"


def _is_online(last_seen: datetime | None, now: datetime) -> bool:
    if last_seen is None:
        return False
    return now - last_seen <= timedelta(minutes=settings.sensor_offline_minutes)


def _parse_filter(value: str | None) -> set[str] | None:
    if value is None:
        return None
    values = {item.strip().upper() for item in value.split(",") if item.strip()}
    return values or None


_ANOMALIES_SAMPLE = [
    {
        "anomaly_id": "ANM-KND-042",
        "sensor_id": "MR-KND-001",
        "zone_id": "ZONE-K1",
        "detected_at": "2026-04-25T20:45:00Z",
        "type": "SUDDEN_SPIKE",
        "description": "Water level rose 0.8m in 10 mins without corresponding rainfall.",
        "severity": "HIGH",
        "anomaly_score": 0.94,
        "reading_at_detection": {
            "water_level_m": 4.2,
            "rate_of_change_m_per_hr": 4.8,
        },
        "expected_range": {"min_m": 1.5, "max_m": 2.8},
        "status": "UNRESOLVED",
        "auto_alert_triggered": True,
        "alert_id": "ALT-KND-001",
    }
]


@router.get("/sensors")
def list_sensors() -> dict:
    now = datetime.now(timezone.utc)
    sensors = fetch_sensors()
    data = []

    for sensor in sensors:
        sensor_id = sensor["sensor_id"]
        reading = get_latest_reading(sensor_id)
        status = get_latest_status(sensor_id)

        last_seen = status.get("last_seen") or reading.get("timestamp")
        online = _is_online(last_seen, now)

        readings_payload = {
            "water_level_m": _to_float(reading.get("water_level_m")),
            "rainfall_mm_per_hr": _to_float(reading.get("rainfall_mm_per_hr")),
            "flow_velocity_mps": _to_float(reading.get("flow_velocity_mps")),
            "temperature_c": _to_float(reading.get("temperature_c")),
            "air_pressure_hpa": _to_float(reading.get("air_pressure_hpa")),
        }

        status_payload = {
            "is_online": online,
            "battery_percent": _to_float(status.get("battery_percent")),
            "signal_strength_dbm": _to_float(status.get("signal_strength_dbm")),
            "last_seen": _to_iso(last_seen) if last_seen else None,
        }

        thresholds = {
            "warning_m": _to_float(sensor.get("warning_m")),
            "critical_m": _to_float(sensor.get("critical_m")),
        }

        item = {
            "sensor_id": sensor_id,
            "name": sensor.get("name"),
            "location": {
                "lat": _to_float(sensor.get("lat")),
                "lng": _to_float(sensor.get("lng")),
                "zone_id": sensor.get("zone_id"),
                "zone_name": sensor.get("zone_name"),
            },
            "readings": readings_payload,
            "thresholds": thresholds,
        }
        item["device_health"] = status_payload
        data.append(item)

    return {
        "status": "success",
        "timestamp": _to_iso(now),
        "count": len(data),
        "data": data,
    }


@router.get("/sensors/{sensor_id}")
def get_sensor(sensor_id: str) -> dict:
    sensor = fetch_sensor(sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found")

    now = datetime.now(timezone.utc)
    reading = get_latest_reading(sensor_id)
    status = get_latest_status(sensor_id)
    last_seen = status.get("last_seen") or reading.get("timestamp")
    online = _is_online(last_seen, now)

    current_reading = {
        "water_level_m": _to_float(reading.get("water_level_m")),
        "rainfall_mm_per_hr": _to_float(reading.get("rainfall_mm_per_hr")),
        "flow_velocity_mps": _to_float(reading.get("flow_velocity_mps")),
        "temperature_c": _to_float(reading.get("temperature_c")),
        "air_pressure_hpa": _to_float(reading.get("air_pressure_hpa")),
        "recorded_at": _to_iso(reading.get("timestamp"))
        if reading.get("timestamp")
        else None,
    }

    return {
        "status": "success",
        "data": {
            "sensor_id": sensor.get("sensor_id"),
            "name": sensor.get("name"),
            "installed_date": _date_to_str(sensor.get("installed_date")),
            "is_active": sensor.get("is_active"),
            "location": {
                "lat": _to_float(sensor.get("lat")),
                "lng": _to_float(sensor.get("lng")),
                "zone_id": sensor.get("zone_id"),
                "address": sensor.get("address"),
            },
            "current_reading": current_reading,
            "device_health": {
                "is_online": online,
                "battery_percent": _to_float(status.get("battery_percent")),
                "signal_strength_dbm": _to_float(status.get("signal_strength_dbm")),
                "last_maintenance": _date_to_str(sensor.get("last_maintenance")),
                "firmware_version": sensor.get("firmware_version"),
            },
            "thresholds": {
                "watch_m": _to_float(sensor.get("watch_m")),
                "advisory_m": _to_float(sensor.get("advisory_m")),
                "warning_m": _to_float(sensor.get("warning_m")),
                "critical_m": _to_float(sensor.get("critical_m")),
            },
        },
    }


@router.get("/sensors/{sensor_id}/history")
def get_sensor_history(
    sensor_id: str,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    interval: str = Query(default="1h"),
) -> dict:
    if fetch_sensor(sensor_id) is None:
        raise HTTPException(status_code=404, detail="Sensor not found")

    try:
        start = _parse_iso(from_)
        stop = _parse_iso(to)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid datetime format") from exc

    now = datetime.now(timezone.utc)
    if stop is None:
        stop = now
    if start is None:
        start = stop - timedelta(hours=24)

    interval = _normalize_interval(interval)
    history = get_history(sensor_id, start, stop, interval)

    water_levels = [
        item["water_level_m"]
        for item in history
        if item["water_level_m"] is not None
    ]
    flow_velocities = [
        item["flow_velocity_mps"]
        for item in history
        if item["flow_velocity_mps"] is not None
    ]
    rainfalls = [
        item["rainfall_mm"] for item in history if item["rainfall_mm"] is not None
    ]

    statistics = {
        "max_water_level_m": max(water_levels) if water_levels else None,
        "min_water_level_m": min(water_levels) if water_levels else None,
        "avg_water_level_m":
        (sum(water_levels) / len(water_levels)) if water_levels else None,
        "total_rainfall_mm": sum(rainfalls) if rainfalls else None,
        "max_flow_velocity_mps": max(flow_velocities) if flow_velocities else None,
    }

    return {
        "status": "success",
        "sensor_id": sensor_id,
        "from": _to_iso(start),
        "to": _to_iso(stop),
        "interval": interval,
        "count": len(history),
        "data": history,
        "statistics": statistics,
    }


@router.get("/sensors/zone/{zone_id}")
def list_zone_sensors(zone_id: str) -> dict:
    zone = fetch_zone(zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found")

    now = datetime.now(timezone.utc)
    sensors = fetch_sensors_by_zone(zone_id)
    data = []

    for sensor in sensors:
        sensor_id = sensor.get("sensor_id")
        reading = get_latest_reading(sensor_id)
        status_info = get_latest_status(sensor_id)
        last_seen = status_info.get("last_seen") or reading.get("timestamp")
        online = _is_online(last_seen, now)

        readings_payload = {
            "water_level_m": _to_float(reading.get("water_level_m")),
            "rainfall_mm_per_hr": _to_float(reading.get("rainfall_mm_per_hr")),
            "flow_velocity_mps": _to_float(reading.get("flow_velocity_mps")),
            "temperature_c": _to_float(reading.get("temperature_c")),
            "air_pressure_hpa": _to_float(reading.get("air_pressure_hpa")),
        }

        status_payload = {
            "device_online": online,
            "battery_percent": _to_float(status_info.get("battery_percent")),
            "signal_strength_dbm": _to_float(status_info.get("signal_strength_dbm")),
            "last_seen": _to_iso(last_seen) if last_seen else None,
        }

        thresholds = {
            "water_level_warning_m": _to_float(sensor.get("warning_m")),
            "water_level_critical_m": _to_float(sensor.get("critical_m")),
        }

        data.append(
            {
                "sensor_id": sensor_id,
                "name": sensor.get("name"),
                "location": {
                    "lat": _to_float(sensor.get("lat")),
                    "lng": _to_float(sensor.get("lng")),
                    "zone_id": sensor.get("zone_id"),
                    "zone_name": sensor.get("zone_name"),
                },
                "readings": readings_payload,
                "status": status_payload,
                "thresholds": thresholds,
            }
        )

    return {
        "status": "success",
        "timestamp": _to_iso(now),
        "zone_id": zone.get("zone_id"),
        "zone_name": zone.get("zone_name"),
        "count": len(data),
        "data": data,
    }


@router.get("/anomalies")
def list_anomalies(
    status: str | None = Query(default=None),
    sensor_id: str | None = Query(default=None),
    severity: str | None = Query(default=None),
) -> dict:
    rows = fetch_anomalies(limit=200)

    items = []
    for r in rows:
        reading = r.get("reading") or {}
        created = r.get("created_at")
        items.append(
            {
                "anomaly_id": r.get("anomaly_id"),
                "sensor_id": r.get("sensor_id"),
                "zone_id": r.get("zone_id"),
                "detected_at": _to_iso(created) if created else None,
                "type": r.get("detection_method") or reading.get("type") or "ANOMALY",
                "description": reading.get("description") or "",
                "severity": r.get("severity"),
                "anomaly_score": reading.get("score"),
                "reading_at_detection": reading,
                "expected_range": reading.get("expected_range"),
                "status": "UNRESOLVED",
                "auto_alert_triggered": reading.get("alert_id") is not None,
                "alert_id": reading.get("alert_id"),
            }
        )

    if sensor_id is not None:
        items = [it for it in items if it.get("sensor_id") == sensor_id]

    status_filter = _parse_filter(status)
    if status_filter:
        items = [it for it in items if str(it.get("status", "")).upper() in status_filter]

    severity_filter = _parse_filter(severity)
    if severity_filter:
        items = [it for it in items if str(it.get("severity", "")).upper() in severity_filter]

    return {"status": "success", "count": len(items), "data": items}


@router.get("/anomalies/{zone_id}")
def list_zone_anomalies(
    zone_id: str,
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
) -> dict:
    zone = fetch_zone(zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found")
    rows = fetch_zone_anomalies(zone_id, limit=200)
    items = []
    for r in rows:
        reading = r.get("reading") or {}
        created = r.get("created_at")
        items.append(
            {
                "anomaly_id": r.get("anomaly_id"),
                "sensor_id": r.get("sensor_id"),
                "zone_id": r.get("zone_id"),
                "detected_at": _to_iso(created) if created else None,
                "type": r.get("detection_method") or reading.get("type") or "ANOMALY",
                "description": reading.get("description") or "",
                "severity": r.get("severity"),
                "anomaly_score": reading.get("score"),
                "reading_at_detection": reading,
                "expected_range": reading.get("expected_range"),
                "status": "UNRESOLVED",
                "auto_alert_triggered": reading.get("alert_id") is not None,
                "alert_id": reading.get("alert_id"),
            }
        )

    status_filter = _parse_filter(status)
    if status_filter:
        items = [it for it in items if str(it.get("status", "")).upper() in status_filter]

    severity_filter = _parse_filter(severity)
    if severity_filter:
        items = [it for it in items if str(it.get("severity", "")).upper() in severity_filter]

    return {
        "status": "success",
        "zone_id": zone.get("zone_id"),
        "zone_name": zone.get("zone_name"),
        "count": len(items),
        "data": items,
    }
