"""Sensor simulator — publishes realistic MQTT payloads for sensors that
have no physical ESP32 yet.  Publishes to flood/a1/<slot> every
PUBLISH_INTERVAL_SEC seconds, drifting readings slowly over time so the
frontend shows live, changing data.
"""

import json
import math
import os
import time
import logging
import uuid

import paho.mqtt.client as mqtt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com")
MQTT_PORT   = int(os.getenv("MQTT_PORT", "1883"))
PUBLISH_INTERVAL_SEC = int(os.getenv("PUBLISH_INTERVAL_SEC", "30"))

# Sensors that need simulation (MR-KND-002 has a real ESP32)
SENSORS = [
    {
        "device_id": "MR-KND-001",
        "topic":     "flood/a1/sensor02",
        "water_level_cm": 225.0,
        "temperature":    27.6,
        "pressure":       1012.8,
        "rainfall":       6.5,
        "flow_velocity":  1.10,
        "battery":        81.0,
        "signal":        -63.0,
        "drift_amp":      8.0,   # drift amplitude in cm
        "drift_period":   900,   # seconds for one full sine cycle
    },
    {
        "device_id": "MR-M3-001",
        "topic":     "flood/a1/sensor03",
        "water_level_cm": 138.0,
        "temperature":    26.8,
        "pressure":       1014.0,
        "rainfall":       1.4,
        "flow_velocity":  0.95,
        "battery":        88.0,
        "signal":        -58.0,
        "drift_amp":      5.0,
        "drift_period":   1200,
    },
    {
        "device_id": "MR-T1-001",
        "topic":     "flood/a1/sensor04",
        "water_level_cm": 205.0,
        "temperature":    27.0,
        "pressure":       1013.1,
        "rainfall":       3.1,
        "flow_velocity":  0.82,
        "battery":        90.0,
        "signal":        -56.0,
        "drift_amp":      6.0,
        "drift_period":   1100,
    },
    {
        "device_id": "MR-X1-001",
        "topic":     "flood/a1/sensor05",
        "water_level_cm": 435.0,
        "temperature":    28.1,
        "pressure":       1010.9,
        "rainfall":       11.2,
        "flow_velocity":  1.32,
        "battery":        74.0,
        "signal":        -69.0,
        "drift_amp":      12.0,
        "drift_period":   800,
    },
    {
        "device_id": "MR-X1-002",
        "topic":     "flood/a1/sensor06",
        "water_level_cm": 312.0,
        "temperature":    27.8,
        "pressure":       1011.4,
        "rainfall":       8.1,
        "flow_velocity":  1.18,
        "battery":        68.0,
        "signal":        -72.0,
        "drift_amp":      10.0,
        "drift_period":   1000,
    },
]


def _build_payload(sensor: dict, t: float) -> dict:
    """Build a sensor payload with slow sine-wave drift so readings aren't static."""
    phase = (t % sensor["drift_period"]) / sensor["drift_period"]
    drift = sensor["drift_amp"] * math.sin(2 * math.pi * phase)

    water_cm = round(sensor["water_level_cm"] + drift, 2)
    # small correlated drifts on other fields
    rain     = round(max(0.0, sensor["rainfall"] + drift * 0.02), 2)
    flow     = round(max(0.0, sensor["flow_velocity"] + drift * 0.001), 3)
    temp     = round(sensor["temperature"] + drift * 0.005, 2)
    pressure = round(sensor["pressure"] - drift * 0.01, 2)

    return {
        "device_id":              sensor["device_id"],
        "timestamp":              int(t * 1_000_000_000),  # nanoseconds
        "temperature":            temp,
        "pressure":               pressure,
        "water_level_cm":         water_cm,
        "rainfall_intensity_mmh": rain,
        "flow_velocity_ms":       flow,
        "device_status": {
            "battery_voltage":     sensor["battery"],
            "signal_strength_dbm": sensor["signal"],
        },
    }


def main() -> None:
    client_id = f"flood-simulator-{uuid.uuid4().hex[:8]}"
    client = mqtt.Client(client_id=client_id)

    def on_connect(c, userdata, flags, rc):
        if rc == 0:
            logger.info("✅ Connected to MQTT broker %s:%s", MQTT_BROKER, MQTT_PORT)
        else:
            logger.error("❌ MQTT connect failed, rc=%s", rc)

    def on_disconnect(c, userdata, rc):
        logger.warning("Disconnected from MQTT (rc=%s), will auto-reconnect", rc)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    logger.info("Connecting to %s:%s …", MQTT_BROKER, MQTT_PORT)
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    client.loop_start()

    logger.info(
        "Simulator started — publishing %d sensors every %ds",
        len(SENSORS), PUBLISH_INTERVAL_SEC,
    )

    while True:
        t = time.time()
        for sensor in SENSORS:
            payload = _build_payload(sensor, t)
            topic   = sensor["topic"]
            message = json.dumps(payload)
            result  = client.publish(topic, message, qos=0)
            if result.rc == 0:
                logger.info(
                    "[SIM→MQTT] %s → %s | Water: %.1fcm | Temp: %.1f°C",
                    sensor["device_id"], topic,
                    payload["water_level_cm"], payload["temperature"],
                )
            else:
                logger.warning("Publish failed for %s rc=%s", sensor["device_id"], result.rc)

        time.sleep(PUBLISH_INTERVAL_SEC)


if __name__ == "__main__":
    main()
