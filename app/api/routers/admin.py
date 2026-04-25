from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/v1/admin", tags=["admin"])


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


class ZoneUpdatePayload(BaseModel):
    geometry: ZoneGeometry


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
    return payload.model_dump()


@router.patch("/sensors/{sensor_id}")
def update_sensor(sensor_id: str, payload: SensorUpdatePayload) -> dict:
    return payload.model_dump()


@router.delete("/sensors/{sensor_id}")
def delete_sensor(sensor_id: str) -> dict:
    return {
        "status": "success",
        "message": f"Sensor {sensor_id} has been successfully deactivated.",
        "deactivated_at": "2026-04-22T23:45:00Z",
        "note": "Historical data preserved for XGBoost model training and audit.",
    }


@router.post("/zones")
def create_zone(payload: ZoneCreatePayload) -> dict:
    return payload.model_dump()


@router.patch("/zones/{zone_id}")
def update_zone(zone_id: str, payload: ZoneUpdatePayload) -> dict:
    return payload.model_dump()


@router.delete("/zones/{zone_id}")
def delete_zone(zone_id: str) -> dict:
    return {
        "status": "success",
        "message": f"Zone {zone_id} deactivated. All historical sensor links preserved for audit.",
    }


@router.post("/shelters")
def create_shelter(payload: ShelterCreatePayload) -> dict:
    return payload.model_dump()


@router.patch("/shelters/{shelter_id}")
def update_shelter(shelter_id: str, payload: ShelterUpdatePayload) -> dict:
    return payload.model_dump()


@router.delete("/shelters/{shelter_id}")
def delete_shelter(shelter_id: str) -> dict:
    return {
        "status": "success",
        "message": f"Shelter {shelter_id} has been removed from the registry. Historical data preserved for audit.",
    }


@router.patch("/anomalies/{anomaly_id}")
def update_anomaly(anomaly_id: str, payload: AnomalyUpdatePayload) -> dict:
    return payload.model_dump()