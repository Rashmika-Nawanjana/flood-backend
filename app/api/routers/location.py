from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.pg import get_connection

router = APIRouter(prefix="/v1/location", tags=["location"])


class LocationResolvePayload(BaseModel):
    lat: float
    lng: float
    clerk_id: Optional[str] = None


@router.post("/resolve")
def resolve_location(payload: LocationResolvePayload) -> dict:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # geometry is stored as GeoJSON JSONB — cast to text for ST_GeomFromGeoJSON.
    # ST_MakePoint expects (longitude, latitude) order.
    zone_query = """
        SELECT zone_id, zone_name, risk_level, risk_score, color_code, active_alerts
        FROM zones
        WHERE geometry IS NOT NULL
          AND ST_Contains(
              ST_SetSRID(ST_GeomFromGeoJSON(geometry::text), 4326),
              ST_SetSRID(ST_MakePoint(%s, %s), 4326)
          )
        LIMIT 1
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(zone_query, (payload.lng, payload.lat))
            row = cur.fetchone()

    if not row:
        return {
            "status": "success",
            "timestamp": timestamp,
            "coordinates": {"lat": payload.lat, "lng": payload.lng},
            "zone": None,
            "message": "Coordinates do not fall within any monitored flood zone.",
            "user_zone_updated": False,
        }

    zone_id = row["zone_id"]
    user_zone_updated = False

    if payload.clerk_id:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET zone_id = %s WHERE clerk_id = %s",
                    (zone_id, payload.clerk_id),
                )
                user_zone_updated = cur.rowcount > 0

    return {
        "status": "success",
        "timestamp": timestamp,
        "coordinates": {"lat": payload.lat, "lng": payload.lng},
        "zone": {
            "zone_id": zone_id,
            "zone_name": row["zone_name"],
            "risk_level": row["risk_level"],
            "risk_score": float(row["risk_score"]) if row["risk_score"] is not None else None,
            "color_code": row["color_code"],
            "active_alerts": row["active_alerts"] or 0,
        },
        "user_zone_updated": user_zone_updated,
    }
