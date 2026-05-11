import os
import json
import threading
import time
import uuid
import logging
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


# Configuration
MQTT_BROKER = _required_env("MQTT_BROKER")
MQTT_PORT = int(_required_env("MQTT_PORT"))
MQTT_TOPIC = _required_env("MQTT_TOPIC")

KAFKA_BROKER = _required_env("KAFKA_BROKER")
KAFKA_TOPIC = _required_env("KAFKA_TOPIC")

# Wait for Kafka to be ready
def wait_for_kafka(max_attempts=30, wait_seconds=2):
    logger.info(f"Waiting for Kafka at {KAFKA_BROKER}...")
    for attempt in range(1, max_attempts + 1):
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BROKER,
                request_timeout_ms=5000,
                api_version_auto_timeout_ms=5000
            )
            producer.close()
            logger.info(f"✅ Kafka ready on attempt {attempt}!")
            return True
        except NoBrokersAvailable:
            logger.warning(f"   Attempt {attempt}/{max_attempts} - waiting {wait_seconds}s...")
            time.sleep(wait_seconds)
        except Exception as e:
            logger.error(f"   Attempt {attempt}/{max_attempts} - {e}")
            time.sleep(wait_seconds)
    return False

# Initialize Kafka producer with batching enabled
def create_producer():
    return KafkaProducer(
        bootstrap_servers=KAFKA_BROKER,
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        batch_size=16384,      # Batch 16KB
        linger_ms=100,         # Wait up to 100ms for batch
        acks='all',            # Wait for all replicas
        retries=3,
    )

producer = None


def normalize_payload(raw: dict) -> dict | None:
    """Map a raw sensor payload to the canonical schema downstream services expect.

    Accepts canonical fields, ESP32 legacy (temp_c/pressure_hpa/distance_cm/rssi_dbm/timestamp_ms),
    or any mix. Always rebuilds the payload so nested device_status keys (battery_charge vs
    battery_voltage, rssi_dbm vs signal_strength_dbm) are remapped consistently.
    Returns None if device_id is missing.
    """
    if "device_id" not in raw:
        return None

    ts = raw.get("timestamp")
    # Sensor uptime (timestamp_ms < 10^12) is not wall-clock — fall back to server time.
    if ts is None or (isinstance(ts, (int, float)) and ts < 10**12):
        ts_ms = raw.get("timestamp_ms")
        if ts_ms is not None and ts_ms >= 10**12:
            ts = ts_ms
        else:
            ts = int(time.time() * 1_000_000_000)  # nanoseconds

    nested_status = raw.get("device_status") if isinstance(raw.get("device_status"), dict) else {}

    return {
        "device_id": raw["device_id"],
        "timestamp": ts,
        "temperature": float(raw.get("temperature", raw.get("temp_c", 0.0))),
        "pressure": float(raw.get("pressure", raw.get("pressure_hpa", 0.0))),
        "water_level_cm": float(raw.get("water_level_cm", raw.get("distance_cm", 0.0))),
        "rainfall_intensity_mmh": float(raw.get("rainfall_intensity_mmh", 0.0)),
        "flow_velocity_ms": float(raw.get("flow_velocity_ms", 0.0)),
        "device_status": {
            "battery_voltage": float(
                nested_status.get("battery_voltage",
                    nested_status.get("battery_charge",
                        raw.get("battery_voltage", raw.get("battery_charge", 0.0))))
            ),
            "signal_strength_dbm": float(
                nested_status.get("signal_strength_dbm",
                    nested_status.get("rssi_dbm",
                        raw.get("signal_strength_dbm", raw.get("rssi_dbm", 0.0))))
            ),
        },
    }

class MQTTClientManager:
    def __init__(self):
        # Unique client_id prevents disconnect loops on shared public brokers (e.g. HiveMQ)
        # where another client with the same id would forcibly take over the session.
        self.client = mqtt.Client(client_id=f"mqtt_kafka_bridge_{uuid.uuid4().hex[:8]}")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.lock = threading.Lock()
        self.connected = False

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("✅ Connected to MQTT broker")
            self.connected = True
            client.subscribe(MQTT_TOPIC)
            logger.info(f"📡 Subscribed to {MQTT_TOPIC}")
        else:
            logger.error(f"❌ MQTT connection failed, code {rc}")

    def on_disconnect(self, client, userdata, rc):
        logger.warning(f"Disconnected from MQTT (code {rc}), attempting reconnect...")
        self.connected = False

    def on_message(self, client, userdata, msg):
        global producer
        try:
            raw = json.loads(msg.payload.decode())
            payload = normalize_payload(raw)
            if payload is None:
                logger.warning(f"Skipped message - no device_id: {raw}")
                return

            with self.lock:
                if producer is None:
                    logger.error("Producer not ready, dropping message")
                    return
                producer.send(KAFKA_TOPIC, value=payload)
                logger.info(
                    f"[MQTT→Kafka] {payload['device_id']} | Water: {payload['water_level_cm']}cm | "
                    f"Temp: {payload['temperature']}°C | Rain: {payload['rainfall_intensity_mmh']}mm/h"
                )
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from MQTT: {msg.payload}")
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    def connect(self):
        try:
            self.client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"Failed to connect to MQTT: {e}")
            return False
        return True

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

def main():
    global producer
    
    logger.info("=" * 60)
    logger.info("🌊 MQTT → KAFKA BRIDGE SERVICE")
    logger.info(f"   MQTT:   {MQTT_BROKER}:{MQTT_PORT}")
    logger.info(f"   Kafka:  {KAFKA_BROKER}")
    logger.info("=" * 60)

    # Wait for Kafka
    if not wait_for_kafka():
        logger.error("❌ Kafka failed to become ready")
        return 1

    # Create producer
    try:
        producer = create_producer()
        logger.info("✅ Kafka producer created with batching enabled")
    except Exception as e:
        logger.error(f"Failed to create Kafka producer: {e}")
        return 1

    # Connect to MQTT
    mqtt_manager = MQTTClientManager()
    if not mqtt_manager.connect():
        logger.error("❌ Failed to connect to MQTT")
        return 1

    logger.info("✅ Pipeline started!")
    logger.info("   MQTT → Kafka bridge active...")
    logger.info("-" * 60)

    try:
        # Keep running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\n👋 Shutting down...")
        mqtt_manager.disconnect()
        if producer:
            producer.flush()
            producer.close()
        logger.info("✅ Done!")
        return 0

if __name__ == "__main__":
    exit(main())
