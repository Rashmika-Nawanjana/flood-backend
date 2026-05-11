from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import psycopg
import uuid
from psycopg.types.json import Json

from app.auth.clerk import require_roles
from app.db.pg import get_connection

router = APIRouter(
    prefix="/v1/admin",
    tags=["admin"],
    dependencies=[Depends(require_roles(["admin", "field_officer"]))],
)


class SensorLocation(BaseModel):
    lat: float
    lng: float
    zone_id: str
    address: str


class SensorThresholds(BaseModel):
    watch_m: float
    advisory_m: float
    warning_m: float
    critical_m: float


class SensorCreatePayload(BaseModel):
    sensor_id: str
    name: str
    location: SensorLocation
    installed_date: str
    firmware_version: str
    thresholds: SensorThresholds


class SensorDeviceHealthUpdate(BaseModel):
    last_maintenance: str
    firmware_version: str


class SensorThresholdsUpdate(BaseModel):
    warning_m: float
    critical_m: float


class SensorUpdatePayload(BaseModel):
    device_health: SensorDeviceHealthUpdate
    thresholds: SensorThresholdsUpdate
    justification: str


class ZoneGeometry(BaseModel):
    type: str
    coordinates: list


class ZoneCreatePayload(BaseModel):
    zone_id: str
    zone_name: str
    geometry: ZoneGeometry
    population_at_risk: int
    description: str
    river_id: int
    prev_zone_id: str | None = None
    next_zone_id: str | None = None


class ZoneUpdatePayload(BaseModel):
    geometry: ZoneGeometry
    river_id: int | None = None
    prev_zone_id: str | None = None
    next_zone_id: str | None = None


class RiverCreatePayload(BaseModel):
    river_name: str


class ShelterCreatePayload(BaseModel):
    zone_id: str
    name: str
    lat: float
    lng: float
    capacity: int
    contact_number: str
    status: str


class ShelterUpdatePayload(BaseModel):
    current_occupancy: int
    status: str


class AnomalyUpdatePayload(BaseModel):
    status: str
    resolution_note: str
    resolved_by: str


@router.post("/sensors")
def create_sensor(payload: SensorCreatePayload) -> dict:
    insert = """
    INSERT INTO sensor_nodes (
        sensor_id, name, zone_id, lat, lng, address, installed_date,
        firmware_version, watch_m, advisory_m, warning_m, critical_m,
        is_active, last_maintenance
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE,%s)
    ON CONFLICT (sensor_id) DO UPDATE SET
      name = EXCLUDED.name,
      zone_id = EXCLUDED.zone_id,
      lat = EXCLUDED.lat,
      lng = EXCLUDED.lng,
      address = EXCLUDED.address,
      installed_date = EXCLUDED.installed_date,
      firmware_version = EXCLUDED.firmware_version,
      watch_m = EXCLUDED.watch_m,
      advisory_m = EXCLUDED.advisory_m,
      warning_m = EXCLUDED.warning_m,
      critical_m = EXCLUDED.critical_m,
      last_maintenance = EXCLUDED.last_maintenance
    RETURNING *
    """
    data = payload.model_dump()
    loc = data["location"]
    thresholds = data["thresholds"]
    params = (
        data["sensor_id"],
        data.get("name"),
        loc.get("zone_id"),
        loc.get("lat"),
        loc.get("lng"),
        loc.get("address"),
        data.get("installed_date"),
        data.get("firmware_version"),
        thresholds.get("watch_m"),
        thresholds.get("advisory_m"),
        thresholds.get("warning_m"),
        thresholds.get("critical_m"),
        None,
    )
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(insert, params)
                row = cur.fetchone()
    except psycopg.errors.ForeignKeyViolation as exc:
        raise HTTPException(
            status_code=400, detail="Invalid zone_id for sensor"
        ) from exc
    return {"status": "success", "data": row}


@router.post("/rivers")
def create_river(payload: RiverCreatePayload) -> dict:
    insert = """
    INSERT INTO rivers (river_name)
    VALUES (%s)
    ON CONFLICT (river_name) DO UPDATE SET
      river_name = EXCLUDED.river_name
    RETURNING *
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(insert, (payload.river_name,))
            row = cur.fetchone()
    return {"status": "success", "data": row}


@router.get("/rivers")
def list_rivers() -> dict:
    query = "SELECT river_id, river_name FROM rivers ORDER BY river_id"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
    return {"status": "success", "count": len(rows), "data": rows}


@router.patch("/sensors/{sensor_id}")
def update_sensor(sensor_id: str, payload: SensorUpdatePayload) -> dict:
    data = payload.model_dump()
    dh = data.get("device_health")
    thr = data.get("thresholds")
    update = """
    UPDATE sensor_nodes SET
      last_maintenance = %s,
      firmware_version = %s,
      warning_m = %s,
      critical_m = %s
    WHERE sensor_id = %s
    RETURNING *
    """
    params = (
        dh.get("last_maintenance") if dh else None,
        dh.get("firmware_version") if dh else None,
        thr.get("warning_m") if thr else None,
        thr.get("critical_m") if thr else None,
        sensor_id,
    )
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(update, params)
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Sensor not found")
    return {"status": "success", "data": row}


@router.delete("/sensors/{sensor_id}")
def delete_sensor(sensor_id: str) -> dict:
    update = "UPDATE sensor_nodes SET is_active = FALSE WHERE sensor_id = %s RETURNING sensor_id"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(update, (sensor_id,))
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Sensor not found")
    return {"status": "success", "message": f"Sensor {sensor_id} deactivated."}


@router.post("/zones")
def create_zone(payload: ZoneCreatePayload) -> dict:
    insert = """
    INSERT INTO zones (
        zone_id, zone_name, geometry, population_at_risk, description,
        river_id, prev_zone_id, next_zone_id, last_updated
    )
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW())
    ON CONFLICT (zone_id) DO UPDATE SET
      zone_name = EXCLUDED.zone_name,
      geometry = EXCLUDED.geometry,
      population_at_risk = EXCLUDED.population_at_risk,
      description = EXCLUDED.description,
      river_id = EXCLUDED.river_id,
      prev_zone_id = EXCLUDED.prev_zone_id,
      next_zone_id = EXCLUDED.next_zone_id,
      last_updated = NOW()
    RETURNING *
    """
    data = payload.model_dump()
    params = (
        data["zone_id"],
        data.get("zone_name"),
        Json(data.get("geometry")),
        data.get("population_at_risk"),
        data.get("description"),
        data.get("river_id"),
        data.get("prev_zone_id"),
        data.get("next_zone_id"),
    )
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(insert, params)
                row = cur.fetchone()
    except psycopg.errors.ForeignKeyViolation as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid river_id, prev_zone_id, or next_zone_id for zone",
        ) from exc
    return {"status": "success", "data": row}


@router.patch("/zones/{zone_id}")
def update_zone(zone_id: str, payload: ZoneUpdatePayload) -> dict:
    data = payload.model_dump()
    update = """
    UPDATE zones SET
        geometry = %s,
        river_id = COALESCE(%s, river_id),
        prev_zone_id = COALESCE(%s, prev_zone_id),
        next_zone_id = COALESCE(%s, next_zone_id),
        last_updated = NOW()
    WHERE zone_id = %s
    RETURNING *
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    update,
                    (
                        Json(data.get("geometry")),
                        data.get("river_id"),
                        data.get("prev_zone_id"),
                        data.get("next_zone_id"),
                        zone_id,
                    ),
                )
                row = cur.fetchone()
    except psycopg.errors.ForeignKeyViolation as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid river_id, prev_zone_id, or next_zone_id for zone",
        ) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Zone not found")
    return {"status": "success", "data": row}


@router.delete("/zones/{zone_id}")
def delete_zone(zone_id: str) -> dict:
    # perform a hard delete for now
    delete = "DELETE FROM zones WHERE zone_id = %s RETURNING zone_id"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(delete, (zone_id,))
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Zone not found")
    return {"status": "success", "message": f"Zone {zone_id} deleted."}


@router.post("/shelters")
def create_shelter(payload: ShelterCreatePayload) -> dict:
    shelter_id = str(uuid.uuid4())
    insert = """
    INSERT INTO zone_shelters (
        shelter_id, zone_id, name, capacity, current_occupancy, lat, lng, distance_km, contact_number, status
    ) VALUES (%s,%s,%s,%s,0,%s,%s,%s,%s,%s)
    RETURNING *
    """
    data = payload.model_dump()
    params = (
        shelter_id,
        data.get("zone_id"),
        data.get("name"),
        data.get("capacity"),
        data.get("lat"),
        data.get("lng"),
        None,
        data.get("contact_number"),
        data.get("status"),
    )
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(insert, params)
            row = cur.fetchone()
    return {"status": "success", "data": row}


@router.patch("/shelters/{shelter_id}")
def update_shelter(shelter_id: str, payload: ShelterUpdatePayload) -> dict:
    data = payload.model_dump()
    update = "UPDATE zone_shelters SET current_occupancy = %s, status = %s WHERE shelter_id = %s RETURNING *"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                update, (data.get("current_occupancy"), data.get("status"), shelter_id)
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Shelter not found")
    return {"status": "success", "data": row}


@router.delete("/shelters/{shelter_id}")
def delete_shelter(shelter_id: str) -> dict:
    delete = "DELETE FROM zone_shelters WHERE shelter_id = %s RETURNING shelter_id"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(delete, (shelter_id,))
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Shelter not found")
    return {"status": "success", "message": f"Shelter {shelter_id} removed."}


@router.patch("/anomalies/{anomaly_id}")
def update_anomaly(anomaly_id: str, payload: AnomalyUpdatePayload) -> dict:
    data = payload.model_dump()
    update = "UPDATE anomalies SET status = %s WHERE anomaly_id = %s RETURNING *"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(update, (data.get("status"), anomaly_id))
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return {"status": "success", "data": row}


import json
import os
from datetime import datetime, timezone

from kafka import KafkaProducer
from pydantic import BaseModel


class AlertResolutionPayload(BaseModel):
    resolution_note: str


_alert_producer: KafkaProducer | None = None


def _get_alert_producer() -> KafkaProducer:
    global _alert_producer
    if _alert_producer is None:
        _alert_producer = KafkaProducer(
            bootstrap_servers=os.getenv("KAFKA_BROKER", "kafka:9092"),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
    return _alert_producer


def _lookup_alert_zone(alert_id: str) -> str | None:
    """Resolve the zone_id for an alert by joining alerts → predictions → zones."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT zone_id FROM alerts WHERE alert_id = %s LIMIT 1
                    """,
                    (alert_id,),
                )
                row = cur.fetchone()
                if row:
                    return row.get("zone_id") if isinstance(row, dict) else row[0]
    except Exception:
        pass
    return None


@router.patch("/alerts/{alert_id}")
def resolve_alert(alert_id: str, payload: AlertResolutionPayload) -> dict:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    zone_id = _lookup_alert_zone(alert_id)
    event = {
        "event": "alert:resolved",
        "timestamp": timestamp,
        "data": {
            "alert_id": alert_id,
            "zone_id": zone_id,
            "resolved_at": timestamp,
            "resolution_note": payload.resolution_note,
        },
    }
    try:
        producer = _get_alert_producer()
        producer.send(os.getenv("SYSTEM_ALERTS_TOPIC", "system.alerts"), event)
        producer.flush()
    except Exception as exc:
        print(f"Failed to publish alert:resolved: {exc}")
    return {"status": "success", "event": "alert:resolved", "data": event["data"]}

