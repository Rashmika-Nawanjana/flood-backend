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
            if event_type in ["alert:new", "alert:resolved", "anomaly:new", "sensor:offline"]:
                await sio.emit(event_type, payload)
    except Exception as e:
        print("Kafka alerts consumer Error: ", e)


async def _kafka_sensor_consumer_loop() -> None:
    try:
        from aiokafka import AIOKafkaConsumer
        import os
        telemetry_topic = os.getenv("TELEMETRY_TOPIC", "telemetry.live")
        consumer = AIOKafkaConsumer(
            telemetry_topic,
            bootstrap_servers='localhost:9092',
            value_deserializer=lambda v: json.loads(v.decode('utf-8'))
        )
        await consumer.start()
        async for msg in consumer:
            payload = msg.value
            event_type = payload.get("event")
            if event_type == "sensor:update":
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