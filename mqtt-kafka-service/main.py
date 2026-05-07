import os
import json
import threading
import time
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


def validate_payload(payload: dict) -> bool:
    """Validate the new MQTT telemetry payload shape."""
    required_fields = [
        "device_id",
        "timestamp",
        "temperature",
        "pressure",
        "water_level_cm",
        "rainfall_intensity_mmh",
        "flow_velocity_ms",
        "device_status",
    ]
    if not all(field in payload for field in required_fields):
        return False

    device_status = payload.get("device_status")
    if not isinstance(device_status, dict):
        return False

    return all(key in device_status for key in ["battery_voltage", "signal_strength_dbm"])

class MQTTClientManager:
    def __init__(self):
        self.client = mqtt.Client(client_id="mqtt_kafka_bridge")
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
            payload = json.loads(msg.payload.decode())
            
            # Validate required fields
            if not validate_payload(payload):
                logger.warning(f"Skipped invalid message - missing fields: {payload}")
                return
            
            with self.lock:
                if producer is None:
                    logger.error("Producer not ready, dropping message")
                    return
                future = producer.send(KAFKA_TOPIC, value=payload)
                # Non-blocking: don't wait for send confirmation
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
