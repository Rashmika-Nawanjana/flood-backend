import asyncio
from datetime import datetime, timezone

import socketio

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = socketio.ASGIApp(sio)

_broadcast_task_started = False
_task_lock = asyncio.Lock()


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _event_payload(event: str, data: dict) -> dict:
    return {"event": event, "timestamp": _now_utc_iso(), "data": data}


async def _emit_initial_snapshot(sid: str) -> None:
    await sio.emit(
        "sensor:update",
        _event_payload(
            "sensor:update",
            {
                "sensor_id": "MR-KND-001",
                "zone_id": "ZONE-K1",
                "current_reading": {
                    "water_level_m": 4.58,
                    "flow_velocity_mps": 0.88,
                    "rainfall_mm_per_hr": 12.0,
                    "temperature_c": 28.5,
                    "air_pressure_hpa": 1011.2,
                    "trend": "RISING",
                },
            },
        ),
        to=sid,
    )
    await sio.emit(
        "zone:risk:update",
        _event_payload(
            "zone:risk:update",
            {
                "zone_id": "ZONE-K1",
                "zone_name": "Getambe Basin",
                "previous_level": "WARNING",
                "current_level": "HIGH",
                "risk_score": 78.4,
                "color_code": "#F97316",
            },
        ),
        to=sid,
    )
    await sio.emit(
        "prediction:new",
        _event_payload(
            "prediction:new",
            {
                "prediction_id": "PRED-KND-001",
                "zone_id": "ZONE-K1",
                "predicted_peak_level_m": 4.8,
                "estimated_flood_time": "2026-04-26T03:00:00Z",
                "severity": "HIGH",
                "top_risk_factors": [
                    {"factor": "Upstream Water Level", "value": "3.9m", "impact": "High"},
                    {"factor": "Flow Velocity", "value": "0.95 m/s", "impact": "Medium"},
                ],
            },
        ),
        to=sid,
    )
    await sio.emit(
        "alert:new",
        _event_payload(
            "alert:new",
            {
                "alert_id": "ALT-KND-001",
                "zone_id": "ZONE-K1",
                "severity": "HIGH",
                "title": "Evacuation Warning: Getambe Lowlands",
                "message": "Water levels rising rapidly. Evacuate to designated shelters.",
                "recommended_action": "EVACUATE",
                "recommended_shelters": [
                    {
                        "shelter_id": "SH-K001",
                        "name": "Getambe Temple Hall",
                        "lat": 7.2715,
                        "lng": 80.6125,
                    }
                ],
            },
        ),
        to=sid,
    )
    await sio.emit(
        "alert:resolved",
        _event_payload(
            "alert:resolved",
            {
                "alert_id": "ALT-KND-001",
                "zone_id": "ZONE-K1",
                "resolved_at": "2026-04-26T06:00:00Z",
                "resolution_note": "Water levels receding. All clear issued.",
            },
        ),
        to=sid,
    )
    await sio.emit(
        "sensor:offline",
        _event_payload(
            "sensor:offline",
            {
                "sensor_id": "MR-KND-002",
                "zone_id": "ZONE-K2",
                "last_seen": "2026-04-26T01:05:00Z",
                "status": "OFFLINE",
            },
        ),
        to=sid,
    )
    await sio.emit(
        "anomaly:new",
        _event_payload(
            "anomaly:new",
            {
                "anomaly_id": "ANM-KND-042",
                "sensor_id": "MR-KND-001",
                "type": "SUDDEN_SPIKE",
                "severity": "HIGH",
                "anomaly_score": 0.94,
                "description": "Unnatural water level spike detected. Data discarded from ML pipeline.",
            },
        ),
        to=sid,
    )


async def _broadcast_loop() -> None:
    tick = 0
    while True:
        await sio.emit(
            "sensor:update",
            _event_payload(
                "sensor:update",
                {
                    "sensor_id": "MR-KND-001",
                    "zone_id": "ZONE-K1",
                    "current_reading": {
                        "water_level_m": round(4.5 + ((tick % 6) * 0.03), 2),
                        "flow_velocity_mps": round(0.84 + ((tick % 4) * 0.02), 2),
                        "rainfall_mm_per_hr": round(8.0 + ((tick % 5) * 1.0), 1),
                        "temperature_c": 28.5,
                        "air_pressure_hpa": 1011.2,
                        "trend": "RISING",
                    },
                },
            ),
        )

        if tick % 3 == 0:
            await sio.emit(
                "zone:risk:update",
                _event_payload(
                    "zone:risk:update",
                    {
                        "zone_id": "ZONE-K1",
                        "zone_name": "Getambe Basin",
                        "previous_level": "WARNING",
                        "current_level": "HIGH",
                        "risk_score": 78.4,
                        "color_code": "#F97316",
                    },
                ),
            )

        if tick % 5 == 0:
            await sio.emit(
                "prediction:new",
                _event_payload(
                    "prediction:new",
                    {
                        "prediction_id": "PRED-KND-001",
                        "zone_id": "ZONE-K1",
                        "predicted_peak_level_m": 4.8,
                        "estimated_flood_time": "2026-04-26T03:00:00Z",
                        "severity": "HIGH",
                        "top_risk_factors": [
                            {
                                "factor": "Upstream Water Level",
                                "value": "3.9m",
                                "impact": "High",
                            },
                            {
                                "factor": "Flow Velocity",
                                "value": "0.95 m/s",
                                "impact": "Medium",
                            },
                        ],
                    },
                ),
            )

        if tick % 7 == 0:
            await sio.emit(
                "alert:new",
                _event_payload(
                    "alert:new",
                    {
                        "alert_id": "ALT-KND-001",
                        "zone_id": "ZONE-K1",
                        "severity": "HIGH",
                        "title": "Evacuation Warning: Getambe Lowlands",
                        "message": "Water levels rising rapidly. Evacuate to designated shelters.",
                        "recommended_action": "EVACUATE",
                        "recommended_shelters": [
                            {
                                "shelter_id": "SH-K001",
                                "name": "Getambe Temple Hall",
                                "lat": 7.2715,
                                "lng": 80.6125,
                            }
                        ],
                    },
                ),
            )

        if tick % 11 == 0:
            await sio.emit(
                "alert:resolved",
                _event_payload(
                    "alert:resolved",
                    {
                        "alert_id": "ALT-KND-001",
                        "zone_id": "ZONE-K1",
                        "resolved_at": _now_utc_iso(),
                        "resolution_note": "Water levels receding. All clear issued.",
                    },
                ),
            )

        if tick % 13 == 0:
            await sio.emit(
                "sensor:offline",
                _event_payload(
                    "sensor:offline",
                    {
                        "sensor_id": "MR-KND-002",
                        "zone_id": "ZONE-K2",
                        "last_seen": "2026-04-26T01:05:00Z",
                        "status": "OFFLINE",
                    },
                ),
            )

        if tick % 17 == 0:
            await sio.emit(
                "anomaly:new",
                _event_payload(
                    "anomaly:new",
                    {
                        "anomaly_id": "ANM-KND-042",
                        "sensor_id": "MR-KND-001",
                        "type": "SUDDEN_SPIKE",
                        "severity": "HIGH",
                        "anomaly_score": 0.94,
                        "description": "Unnatural water level spike detected. Data discarded from ML pipeline.",
                    },
                ),
            )

        tick += 1
        await asyncio.sleep(12)


async def _ensure_background_task() -> None:
    global _broadcast_task_started
    async with _task_lock:
        if not _broadcast_task_started:
            sio.start_background_task(_broadcast_loop)
            _broadcast_task_started = True


@sio.event
async def connect(sid: str, environ: dict, auth: dict | None) -> None:
    await _ensure_background_task()
    await _emit_initial_snapshot(sid)


@sio.event
async def disconnect(sid: str) -> None:
    return None