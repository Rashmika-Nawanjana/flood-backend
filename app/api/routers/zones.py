from fastapi import APIRouter

router = APIRouter(prefix="/v1", tags=["zones"])


@router.get("/zones")
def list_zones() -> dict:
    zones = [
        {
            "zone_id": "ZONE-4",
            "zone_name": "Kolonnawa Basin",
            "description": "Lower Mahaweli region near Peradeniya",
            "risk_level": "HIGH",
            "risk_score": 78.4,
            "color_code": "#F97316",
            "population_at_risk": 45200,
            "sensors_in_zone": ["KR-001", "KR-002", "KR-003"],
            "active_alerts": 2,
            "last_updated": "2026-04-23T21:20:00Z",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [79.85, 6.91],
                        [79.87, 6.91],
                        [79.87, 6.94],
                        [79.85, 6.94],
                        [79.85, 6.91],
                    ]
                ],
            },
            "current_conditions": {
                "avg_water_level_m": 3.2,
                "max_water_level_m": 3.8,
                "avg_flow_velocity_mps": 0.95,
                "total_rainfall_mm": 145.2,
                "trend": "RISING",
            },
        }
    ]

    return {
        "status": "success",
        "timestamp": "2026-04-23T21:24:00Z",
        "count": len(zones),
        "data": zones,
    }


@router.get("/zones/{zone_id}")
def get_zone(zone_id: str) -> dict:
    return {
        "status": "success",
        "data": {
            "zone_id": zone_id,
            "zone_name": "Getambe Basin",
            "description": "Lower Mahaweli region near Peradeniya",
            "risk_level": "HIGH",
            "risk_score": 78.4,
            "color_code": "#F97316",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [80.61, 7.27],
                        [80.62, 7.27],
                        [80.62, 7.28],
                        [80.61, 7.28],
                        [80.61, 7.27],
                    ]
                ],
            },
            "prediction": {
                "flood_probability_percent": 82.3,
                "predicted_peak_level_m": 4.8,
                "estimated_flood_time": "2026-04-25T23:45:00Z",
                "confidence_percent": 87.1,
                "model_version": "v3.2.1-xgboost",
            },
            "current_conditions": {
                "avg_water_level_m": 3.2,
                "max_water_level_m": 3.8,
                "avg_flow_velocity_mps": 0.95,
                "total_rainfall_mm": 145.2,
                "trend": "RISING",
            },
            "population_at_risk": 20500,
            "shelters": [
                {
                    "shelter_id": "SH-K001",
                    "name": "Getambe Temple Hall",
                    "capacity": 400,
                    "current_occupancy": 150,
                    "lat": 7.2715,
                    "lng": 80.6125,
                    "distance_km": 0.8,
                    "contact_number": "+94812222222",
                }
            ],
        },
    }
