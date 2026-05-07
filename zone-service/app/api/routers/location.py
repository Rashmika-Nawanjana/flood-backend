from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.zone_data import fetch_zones, normalize_zone_row

router = APIRouter(prefix="/v1", tags=["zones"])


def _to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _point_in_ring(lng: float, lat: float, ring: list[list[float]]) -> bool:
    if len(ring) < 3:
        return False
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        try:
            xi, yi = float(ring[i][0]), float(ring[i][1])
            xj, yj = float(ring[j][0]), float(ring[j][1])
        except (TypeError, ValueError, IndexError):
            j = i
            continue
        if (yi > lat) != (yj > lat):
            denom = yj - yi
            if denom != 0:
                x_intersect = (xj - xi) * (lat - yi) / denom + xi
                if lng < x_intersect:
                    inside = not inside
        j = i
    return inside


def _point_in_polygon(lng: float, lat: float, coords: list[list[list[float]]]) -> bool:
    if not coords:
        return False
    return _point_in_ring(lng, lat, coords[0])


def _geometry_contains(geometry: dict[str, Any], lng: float, lat: float) -> bool:
    if not geometry:
        return False
    geometry_type = geometry.get("type")
    coords = geometry.get("coordinates")
    if geometry_type == "Polygon":
        return _point_in_polygon(lng, lat, coords or [])
    if geometry_type == "MultiPolygon":
        for polygon in coords or []:
            if _point_in_polygon(lng, lat, polygon):
                return True
    return False


class LocationResolvePayload(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


@router.post("/location/resolve")
def resolve_location(payload: LocationResolvePayload) -> dict:
    now = datetime.now(timezone.utc)
    rows = fetch_zones()

    for row in rows:
        zone = normalize_zone_row(row)
        geometry = zone.get("geometry") or {}
        if _geometry_contains(geometry, payload.lng, payload.lat):
            return {
                "status": "success",
                "timestamp": _to_iso(now),
                "coordinates": {"lat": payload.lat, "lng": payload.lng},
                "zone": {
                    "zone_id": zone.get("zone_id"),
                    "zone_name": zone.get("zone_name"),
                    "risk_level": zone.get("risk_level"),
                    "risk_score": zone.get("risk_score"),
                    "color_code": zone.get("color_code"),
                    "active_alerts": zone.get("active_alerts"),
                },
            }

    return {
        "status": "success",
        "timestamp": _to_iso(now),
        "coordinates": {"lat": payload.lat, "lng": payload.lng},
        "zone": None,
        "message": "Coordinates do not fall within any monitored flood zone.",
    }
