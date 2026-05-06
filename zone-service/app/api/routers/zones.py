from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from app.services.zone_data import (
    fetch_zone,
    fetch_zone_shelters,
    fetch_zones,
    get_zone_conditions,
    normalize_zone_row,
)

router = APIRouter(prefix="/v1", tags=["zones"])


def _to_float(value):
    if isinstance(value, Decimal):
        return float(value)
    return value


def _to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_conditions(payload: dict | None) -> dict:
    payload = payload or {}
    return {
        "avg_water_level_m": _to_float(payload.get("avg_water_level_m")),
        "max_water_level_m": _to_float(payload.get("max_water_level_m")),
        "avg_flow_velocity_mps": _to_float(payload.get("avg_flow_velocity_mps")),
        "total_rainfall_mm": _to_float(payload.get("total_rainfall_mm")),
        "trend": payload.get("trend"),
    }


def _normalize_prediction(payload: dict | None) -> dict:
    payload = payload or {}
    return {
        "flood_probability_percent": _to_float(
            payload.get("flood_probability_percent")
        ),
        "predicted_peak_level_m": _to_float(payload.get("predicted_peak_level_m")),
        "estimated_flood_time": payload.get("estimated_flood_time"),
        "confidence_percent": _to_float(payload.get("confidence_percent")),
        "model_version": payload.get("model_version"),
    }


@router.get("/zones")
def list_zones() -> dict:
    now = datetime.now(timezone.utc)
    rows = fetch_zones()
    data = []

    for row in rows:
        zone = normalize_zone_row(row)
        influx_conditions = get_zone_conditions(zone["zone_id"])
        conditions_payload = _normalize_conditions(
            influx_conditions or zone.get("current_conditions")
        )

        data.append(
            {
                "zone_id": zone["zone_id"],
                "zone_name": zone["zone_name"],
                "description": zone["description"],
                "risk_level": zone["risk_level"],
                "risk_score": zone["risk_score"],
                "color_code": zone["color_code"],
                "population_at_risk": zone["population_at_risk"],
                "sensors_in_zone": zone.get("sensors_in_zone", []),
                "active_alerts": zone["active_alerts"],
                "last_updated": zone["last_updated"],
                "geometry": zone["geometry"],
                "current_conditions": conditions_payload,
            }
        )

    return {
        "status": "success",
        "timestamp": _to_iso(now),
        "count": len(data),
        "data": data,
    }


@router.get("/zones/{zone_id}")
def get_zone(zone_id: str) -> dict:
    row = fetch_zone(zone_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Zone not found")

    zone = normalize_zone_row(row)
    influx_conditions = get_zone_conditions(zone_id)
    conditions_payload = _normalize_conditions(
        influx_conditions or zone.get("current_conditions")
    )
    prediction_payload = _normalize_prediction(zone.get("prediction"))
    shelters = fetch_zone_shelters(zone_id)

    return {
        "status": "success",
        "data": {
            "zone_id": zone["zone_id"],
            "zone_name": zone["zone_name"],
            "description": zone["description"],
            "risk_level": zone["risk_level"],
            "risk_score": zone["risk_score"],
            "color_code": zone["color_code"],
            "geometry": zone["geometry"],
            "prediction": prediction_payload,
            "current_conditions": conditions_payload,
            "population_at_risk": zone["population_at_risk"],
            "shelters": [
                {
                    "shelter_id": shelter.get("shelter_id"),
                    "name": shelter.get("name"),
                    "capacity": shelter.get("capacity"),
                    "current_occupancy": shelter.get("current_occupancy"),
                    "lat": _to_float(shelter.get("lat")),
                    "lng": _to_float(shelter.get("lng")),
                    "distance_km": _to_float(shelter.get("distance_km")),
                    "contact_number": shelter.get("contact_number"),
                }
                for shelter in shelters
            ],
        },
    }
