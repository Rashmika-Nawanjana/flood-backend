from fastapi import APIRouter, Query

router = APIRouter(prefix="/v1", tags=["sensors"])


@router.get("/sensors")
def list_sensors() -> dict:
    sensors = [
        {
            "sensor_id": "MR-KND-001",
            "name": "Mahaweli River - Getambe Bridge",
            "location": {
                "lat": 7.2721,
                "lng": 80.6132,
                "zone_id": "ZONE-K1",
                "zone_name": "Getambe Basin",
            },
            "readings": {
                "water_level_m": 4.53,
                "rainfall_mm_per_hr": 8.2,
                "flow_velocity_mps": 0.85,
                "temperature_c": 28.5,
                "air_pressure_hpa": 1011.2,
            },
            "device_health": {
                "is_online": True,
                "battery_percent": 75,
                "signal_strength_dbm": -68,
                "last_seen": "2026-04-22T23:04:12Z",
            },
            "thresholds": {
                "warning_m": 5.0,
                "critical_m": 6.5,
            },
        },
        {
            "sensor_id": "MR-KND-002",
            "name": "Mahaweli River - Peradeniya",
            "location": {
                "lat": 7.252,
                "lng": 80.5921,
                "zone_id": "ZONE-K2",
                "zone_name": "Peradeniya Basin",
            },
            "readings": {
                "water_level_m": 2.1,
                "rainfall_mm_per_hr": 0.0,
                "flow_velocity_mps": 0.42,
                "temperature_c": 27.8,
                "air_pressure_hpa": 1012.5,
            },
            "device_health": {
                "is_online": True,
                "battery_percent": 92,
                "signal_strength_dbm": -55,
                "last_seen": "2026-04-22T23:00:05Z",
            },
            "thresholds": {
                "warning_m": 3.5,
                "critical_m": 5.0,
            },
        },
    ]

    return {
        "status": "success",
        "timestamp": "2026-04-22T23:05:00Z",
        "count": len(sensors),
        "data": sensors,
    }


@router.get("/sensors/{sensor_id}")
def get_sensor(sensor_id: str) -> dict:
    return {
        "status": "success",
        "data": {
            "sensor_id": sensor_id,
            "name": "Mahaweli River - Getambe Bridge",
            "installed_date": "2025-11-20",
            "is_active": True,
            "location": {
                "lat": 7.2721,
                "lng": 80.6132,
                "zone_id": "ZONE-K1",
                "address": "Under Getambe Bridge, Peradeniya Road, Kandy",
            },
            "current_reading": {
                "water_level_m": 4.53,
                "rainfall_mm_per_hr": 8.2,
                "flow_velocity_mps": 0.85,
                "temperature_c": 28.5,
                "air_pressure_hpa": 1011.2,
                "recorded_at": "2026-04-22T23:36:12Z",
            },
            "device_health": {
                "is_online": True,
                "battery_percent": 75,
                "signal_strength_dbm": -68,
                "last_maintenance": "2026-03-10",
                "firmware_version": "v1.0.2-esp32",
            },
            "thresholds": {
                "watch_m": 3.5,
                "advisory_m": 4.5,
                "warning_m": 5.0,
                "critical_m": 6.5,
            },
        },
    }


@router.get("/sensors/{sensor_id}/history")
def get_sensor_history(sensor_id: str) -> dict:
    history = [
        {
            "timestamp": "2026-04-21T00:00:00Z",
            "water_level_m": 2.15,
            "rainfall_mm": 0.0,
            "flow_velocity_mps": 0.45,
            "temperature_c": 24.5,
            "air_pressure_hpa": 1012.1,
        },
        {
            "timestamp": "2026-04-21T01:00:00Z",
            "water_level_m": 2.18,
            "rainfall_mm": 0.2,
            "flow_velocity_mps": 0.48,
            "temperature_c": 24.2,
            "air_pressure_hpa": 1011.8,
        },
        {
            "timestamp": "2026-04-21T02:00:00Z",
            "water_level_m": 2.22,
            "rainfall_mm": 0.5,
            "flow_velocity_mps": 0.52,
            "temperature_c": 24.0,
            "air_pressure_hpa": 1011.5,
        },
    ]

    return {
        "status": "success",
        "sensor_id": sensor_id,
        "interval": "1h",
        "from": "2026-04-21T00:00:00Z",
        "to": "2026-04-22T00:00:00Z",
        "count": len(history),
        "data": history,
        "statistics": {
            "max_water_level_m": 4.53,
            "min_water_level_m": 2.1,
            "avg_water_level_m": 2.85,
            "total_rainfall_mm": 45.2,
            "max_flow_velocity_mps": 1.12,
        },
    }


@router.get("/anomalies")
def list_anomalies(
    status: str | None = Query(default=None), sensor_id: str | None = Query(default=None)
) -> dict:
    anomalies = [
        {
            "anomaly_id": "ANM-KND-042",
            "sensor_id": "MR-KND-001",
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

    if status is not None:
        anomalies = [item for item in anomalies if item["status"] == status]
    if sensor_id is not None:
        anomalies = [item for item in anomalies if item["sensor_id"] == sensor_id]

    return {"status": "success", "count": len(anomalies), "data": anomalies}
