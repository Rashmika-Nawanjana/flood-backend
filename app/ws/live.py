import asyncio
import json
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


async def _kafka_consumer_loop() -> None:
    try:
        from aiokafka import AIOKafkaConsumer
        consumer = AIOKafkaConsumer(
            'analytics.predictions',
            bootstrap_servers='localhost:9092',
            value_deserializer=lambda v: json.loads(v.decode('utf-8'))
        )
        await consumer.start()
        async for msg in consumer:
            payload = msg.value
            event_type = payload.get("event")
            if event_type in ["zone:risk:update", "prediction:new"]:
                await sio.emit(event_type, payload)
    except Exception as e:
        print("Kafka consumer Error: ", e)

async def _kafka_alerts_consumer_loop() -> None:
    try:
        from aiokafka import AIOKafkaConsumer
        consumer = AIOKafkaConsumer(
            'system.alerts',
            bootstrap_servers='localhost:9092',
            value_deserializer=lambda v: json.loads(v.decode('utf-8'))
        )
        await consumer.start()
        async for msg in consumer:
            payload = msg.value
            event_type = payload.get("event")
            if event_type in ["alert:new", "alert:resolved", "anomaly:new"]:
                await sio.emit(event_type, payload)
    except Exception as e:
        print("Kafka alerts consumer Error: ", e)

async def _kafka_sensor_consumer_loop() -> None:
    try:
        from aiokafka import AIOKafkaConsumer
        consumer = AIOKafkaConsumer(
            'flood-sensor-data',
            bootstrap_servers='localhost:9092',
            value_deserializer=lambda v: json.loads(v.decode('utf-8'))
        )
        await consumer.start()
        async for msg in consumer:
            raw_data = msg.value
            if "device_id" in raw_data:
                # Transform raw telemetry to frontend format
                payload = {
                    "event": "sensor:update",
                    "timestamp": raw_data.get("timestamp", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
                    "data": {
                        "sensor_id": raw_data["device_id"],
                        "zone_id": "ZONE-K1",  # Placeholder or map from device_id in real implementation
                        "current_reading": {
                            "water_level_m": float(raw_data.get("water_level_cm", 0)) / 100.0,
                            "flow_velocity_mps": raw_data.get("flow_velocity_ms", 0.0),
                            "rainfall_mm_per_hr": raw_data.get("rainfall_intensity_mmh", 0.0),
                            "temperature_c": raw_data.get("temperature", 0.0),
                            "air_pressure_hpa": raw_data.get("pressure", 0.0),
                            "trend": "STABLE"  # Mocked, could be computed based on past readings
                        }
                    }
                }
                await sio.emit("sensor:update", payload)
    except Exception as e:
        print("Kafka sensor telemetry consumer Error: ", e)

async def _ensure_background_task() -> None:
    global _broadcast_task_started
    async with _task_lock:
        if not _broadcast_task_started:
            # We removed the mock simulation _broadcast_loop
            sio.start_background_task(_kafka_consumer_loop)
            sio.start_background_task(_kafka_alerts_consumer_loop)
            sio.start_background_task(_kafka_sensor_consumer_loop)
            _broadcast_task_started = True

@sio.event
async def connect(sid: str, environ: dict, auth: dict | None) -> None:
    await _ensure_background_task()
    # Note: Initial snapshot logic could be restored here querying real DB Data if required
    # await _emit_initial_snapshot(sid)

@sio.event
async def disconnect(sid: str) -> None:
    return None