"""Socket.IO live event server — fans Kafka topics out to connected clients.

Consumes 4 Kafka topics in parallel and emits the 7 events defined in
docs/ws.txt (Real-Time WebSocket Contract):

  telemetry.live       → sensor:update
  analytics.predictions → zone:risk:update, prediction:new
  system.alerts        → alert:new, alert:resolved, sensor:offline
  system.diagnostics   → anomaly:new

Upstream services publish events already shaped per contract — this module
only injects the sensor→zone mapping (postgres lookup, cached) when missing
and runs an offline watchdog that emits sensor:offline after 5 minutes of
silence on telemetry.live.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import psycopg
import socketio
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

logger = logging.getLogger(__name__)

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
DATABASE_URL = os.getenv("DATABASE_URL", "")
# strip SQLAlchemy driver prefix for psycopg
if DATABASE_URL.startswith("postgresql+psycopg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://", 1)

TELEMETRY_TOPIC = os.getenv("TELEMETRY_TOPIC", "telemetry.live")
ANALYTICS_TOPIC = os.getenv("ANALYTICS_PREDICTIONS_TOPIC", "analytics.predictions")
ALERTS_TOPIC = os.getenv("SYSTEM_ALERTS_TOPIC", "system.alerts")
DIAGNOSTICS_TOPIC = os.getenv("DIAGNOSTICS_TOPIC", "system.diagnostics")

OFFLINE_THRESHOLD_SECONDS = int(os.getenv("SENSOR_OFFLINE_THRESHOLD_SEC", "300"))
WATCHDOG_INTERVAL_SECONDS = int(os.getenv("SENSOR_WATCHDOG_INTERVAL_SEC", "60"))

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = socketio.ASGIApp(sio)

_tasks_started = False
_task_lock = asyncio.Lock()
_sensor_last_seen: dict[str, datetime] = {}
_zone_cache: dict[str, str] = {}
_zone_cache_lock = asyncio.Lock()
_producer: AIOKafkaProducer | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def _lookup_zone(sensor_id: str) -> str | None:
    """Look up zone_id for a sensor, cached in-memory for the process lifetime."""
    if sensor_id in _zone_cache:
        return _zone_cache[sensor_id]
    if not DATABASE_URL:
        return None
    async with _zone_cache_lock:
        if sensor_id in _zone_cache:
            return _zone_cache[sensor_id]
        try:
            def _fetch() -> str | None:
                with psycopg.connect(DATABASE_URL) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT zone_id FROM sensors WHERE sensor_id = %s LIMIT 1",
                            (sensor_id,),
                        )
                        row = cur.fetchone()
                        return row[0] if row else None
            zone_id = await asyncio.to_thread(_fetch)
            if zone_id:
                _zone_cache[sensor_id] = zone_id
            return zone_id
        except Exception as exc:
            logger.warning("zone lookup failed for %s: %s", sensor_id, exc)
            return None


async def _inject_zone_id(payload: dict[str, Any], sensor_key: str = "sensor_id") -> None:
    data = payload.get("data") or {}
    if data.get("zone_id"):
        return
    sid = data.get(sensor_key) or data.get("device_id")
    if not sid:
        return
    zone_id = await _lookup_zone(sid)
    if zone_id:
        data["zone_id"] = zone_id
        payload["data"] = data


def _build_consumer(topic: str) -> AIOKafkaConsumer:
    return AIOKafkaConsumer(
        topic,
        bootstrap_servers=KAFKA_BROKER,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="latest",
        enable_auto_commit=True,
        group_id=f"ws-live-{topic}",
    )


async def _telemetry_loop() -> None:
    consumer = _build_consumer(TELEMETRY_TOPIC)
    try:
        await consumer.start()
        logger.info("ws telemetry consumer subscribed to %s", TELEMETRY_TOPIC)
        async for msg in consumer:
            payload = msg.value
            if not isinstance(payload, dict):
                continue
            sid = (payload.get("data") or {}).get("sensor_id")
            if sid:
                _sensor_last_seen[sid] = datetime.now(timezone.utc)
            await _inject_zone_id(payload)
            await sio.emit("sensor:update", payload)
    except Exception:
        logger.exception("telemetry consumer crashed")
    finally:
        try:
            await consumer.stop()
        except Exception:
            pass


async def _analytics_loop() -> None:
    consumer = _build_consumer(ANALYTICS_TOPIC)
    try:
        await consumer.start()
        logger.info("ws analytics consumer subscribed to %s", ANALYTICS_TOPIC)
        async for msg in consumer:
            payload = msg.value
            if not isinstance(payload, dict):
                continue
            event = payload.get("event")
            if event in ("zone:risk:update", "prediction:new"):
                await sio.emit(event, payload)
    except Exception:
        logger.exception("analytics consumer crashed")
    finally:
        try:
            await consumer.stop()
        except Exception:
            pass


async def _alerts_loop() -> None:
    consumer = _build_consumer(ALERTS_TOPIC)
    try:
        await consumer.start()
        logger.info("ws alerts consumer subscribed to %s", ALERTS_TOPIC)
        async for msg in consumer:
            payload = msg.value
            if not isinstance(payload, dict):
                continue
            event = payload.get("event")
            if event in ("alert:new", "alert:resolved"):
                await _inject_zone_id(payload)
                await sio.emit(event, payload)
            elif event == "sensor:offline":
                await _inject_zone_id(payload)
                await sio.emit(event, payload)
    except Exception:
        logger.exception("alerts consumer crashed")
    finally:
        try:
            await consumer.stop()
        except Exception:
            pass


async def _diagnostics_loop() -> None:
    consumer = _build_consumer(DIAGNOSTICS_TOPIC)
    try:
        await consumer.start()
        logger.info("ws diagnostics consumer subscribed to %s", DIAGNOSTICS_TOPIC)
        async for msg in consumer:
            payload = msg.value
            if not isinstance(payload, dict):
                continue
            if payload.get("event") == "anomaly:new":
                await _inject_zone_id(payload)
                await sio.emit("anomaly:new", payload)
    except Exception:
        logger.exception("diagnostics consumer crashed")
    finally:
        try:
            await consumer.stop()
        except Exception:
            pass


async def _watchdog_loop() -> None:
    """Emit sensor:offline when a sensor has been silent for >5 min on telemetry.live."""
    global _producer
    try:
        _producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await _producer.start()
        while True:
            await asyncio.sleep(WATCHDOG_INTERVAL_SECONDS)
            now = datetime.now(timezone.utc)
            stale = [
                (sid, ts)
                for sid, ts in list(_sensor_last_seen.items())
                if (now - ts).total_seconds() > OFFLINE_THRESHOLD_SECONDS
            ]
            for sid, last_seen in stale:
                zone_id = await _lookup_zone(sid)
                event = {
                    "event": "sensor:offline",
                    "timestamp": _now_iso(),
                    "data": {
                        "sensor_id": sid,
                        "zone_id": zone_id,
                        "last_seen": last_seen.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "status": "OFFLINE",
                    },
                }
                try:
                    await _producer.send_and_wait(ALERTS_TOPIC, event)
                except Exception as exc:
                    logger.warning("watchdog publish failed for %s: %s", sid, exc)
                # Stop tracking so we don't spam — re-arms on next telemetry arrival
                _sensor_last_seen.pop(sid, None)
    except Exception:
        logger.exception("watchdog crashed")


async def _ensure_tasks() -> None:
    global _tasks_started
    async with _task_lock:
        if _tasks_started:
            return
        sio.start_background_task(_telemetry_loop)
        sio.start_background_task(_analytics_loop)
        sio.start_background_task(_alerts_loop)
        sio.start_background_task(_diagnostics_loop)
        sio.start_background_task(_watchdog_loop)
        _tasks_started = True
        logger.info("ws live: background consumers started (broker=%s)", KAFKA_BROKER)


@sio.event
async def connect(sid: str, environ: dict, auth: dict | None) -> None:
    await _ensure_tasks()


@sio.event
async def disconnect(sid: str) -> None:
    return None
