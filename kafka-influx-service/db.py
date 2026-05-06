import logging
import uuid

import psycopg
from psycopg.types.json import Json

from config import DATABASE_URL
from schema import parse_timestamp_to_datetime

logger = logging.getLogger(__name__)


def save_anomaly_to_db(data: dict, anomaly_type: str, severity: str, anomaly_score: float | None) -> None:
    if not DATABASE_URL:
        logger.warning("DATABASE_URL not set; skipping anomaly persistence")
        return

    anomaly_id = str(uuid.uuid4())
    sensor_id = data.get("device_id")
    detected_at = parse_timestamp_to_datetime(data.get("timestamp"))
    reading = {
        "device_id": data.get("device_id"),
        "timestamp": data.get("timestamp"),
        "temperature": data.get("temperature"),
        "pressure": data.get("pressure"),
        "water_level_cm": data.get("water_level_cm"),
        "rainfall_intensity_mmh": data.get("rainfall_intensity_mmh"),
        "flow_velocity_ms": data.get("flow_velocity_ms"),
        "device_status": data.get("device_status"),
    }

    insert = """
    INSERT INTO anomalies (
        anomaly_id, sensor_id, zone_id, detected_at, type, severity, anomaly_score, reading, status
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    params = (
        anomaly_id,
        sensor_id,
        None,
        detected_at,
        anomaly_type,
        severity,
        anomaly_score,
        Json(reading),
        "UNRESOLVED",
    )

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(insert, params)
            conn.commit()
        logger.info(f"[Anomaly DB] ✅ Saved anomaly {anomaly_id} for sensor {sensor_id}")
    except psycopg.errors.ForeignKeyViolation:
        logger.warning(f"[Anomaly DB] Sensor {sensor_id} not found; skipping DB insert")
    except Exception as exc:
        logger.error(f"[Anomaly DB] Failed to save anomaly: {exc}")
