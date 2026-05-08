from fastapi import APIRouter, Query

router = APIRouter(prefix="/v1", tags=["intelligence"])


@router.get("/predictions")
def list_predictions(
    severity: str | None = Query(default=None),
    zone_id: str | None = Query(default=None),
    timeframe: str | None = Query(default=None),
) -> dict:
    predictions = [
        {
            "prediction_id": "PRED-KND-001",
            "zone_id": "ZONE-K1",
            "zone_name": "Getambe Basin",
            "created_at": "2026-04-25T19:30:00Z",
            "prediction_window": {
                "from": "2026-04-25T20:00:00Z",
                "to": "2026-04-26T08:00:00Z",
            },
            "flood_probability_percent": 82.3,
            "predicted_peak_level_m": 4.8,
            "estimated_flood_time": "2026-04-25T23:45:00Z",
            "severity": "HIGH",
            "confidence_percent": 87.1,
            "model_version": "XGB-v1.0",
            "top_risk_factors": [
                {"factor": "Upstream Water Level", "value": "3.9m", "impact": "High"},
                {"factor": "Rainfall (Last 6h)", "value": "145.2mm", "impact": "High"},
                {"factor": "Flow Velocity", "value": "0.95 m/s", "impact": "Medium"},
            ],
        }
    ]

    if severity is not None:
        requested_severities = {item.strip().upper() for item in severity.split(",") if item.strip()}
        predictions = [item for item in predictions if item["severity"] in requested_severities]
    if zone_id is not None:
        predictions = [item for item in predictions if item["zone_id"] == zone_id]
    if timeframe is not None and timeframe != "next_24h":
        predictions = []

    return {"status": "success", "count": len(predictions), "data": predictions}


@router.get("/alerts")
def list_alerts() -> dict:
    alerts = [
        {
            "alert_id": "ALT-KND-001",
            "zone_id": "ZONE-K1",
            "zone_name": "Getambe Basin",
            "source_prediction_id": "PRED-KND-001",
            "severity": "HIGH",
            "severity_code": 3,
            "title": "Evacuation Warning: Getambe Lowlands",
            "message": "Water levels are rising rapidly. Please evacuate to the nearest designated shelter immediately.",
            "triggered_at": "2026-04-25T20:00:00Z",
            "triggered_by": "XGBOOST_AUTOMATED",
            "status": "ACTIVE",
            "resolved_at": None,
            "affected_population": 12500,
            "recommended_action": "EVACUATE",
            "recommended_shelters": [
                {
                    "shelter_id": "SH-K001",
                    "name": "Getambe Temple Hall",
                    "lat": 7.2715,
                    "lng": 80.6125,
                }
            ],
            "notifications_sent": {"push": 1200, "sms": 800, "email": 50},
        }
    ]

    return {"status": "success", "count": len(alerts), "data": alerts}


