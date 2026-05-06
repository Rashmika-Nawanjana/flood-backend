import os
import json
import time
import logging
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import NoBrokersAvailable, KafkaError
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime, timezone
import numpy as np
from typing import Dict, List

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


class AnomalyDetector:
    """Statistical anomaly detector using Z-score method."""

    def __init__(self, history_size: int = 10, z_threshold: float = 3.0):
        self.history_size = history_size
        self.z_threshold = z_threshold
        self.recent_readings: Dict[str, List[float]] = {}

    def is_anomaly(self, sensor_id: str, new_value: float) -> bool:
        """
        Detect if sensor reading is a statistical anomaly using Z-score.
        
        Args:
            sensor_id: Unique sensor identifier
            new_value: New water level reading (cm)
            
        Returns:
            True if anomalous, False otherwise
        """
        if sensor_id not in self.recent_readings:
            self.recent_readings[sensor_id] = []

        history = self.recent_readings[sensor_id]

        # Need at least 5 data points to establish baseline
        if len(history) < 5:
            history.append(new_value)
            return False

        # Calculate Z-score
        mean = np.mean(history)
        std_dev = np.std(history)
        z_score = abs(new_value - mean) / (std_dev + 1e-5)

        logger.debug(
            f"Sensor {sensor_id}: value={new_value:.1f}cm, mean={mean:.1f}, "
            f"std={std_dev:.2f}, z-score={z_score:.2f}"
        )

        # Z > 3 indicates anomaly (99.7% confidence)
        if z_score > self.z_threshold:
            logger.warning(
                f"🚨 ANOMALY: Sensor {sensor_id} reading {new_value}cm "
                f"(z-score: {z_score:.2f})"
            )
            return True

        # Update history for normal readings
        history.append(new_value)
        if len(history) > self.history_size:
            history.pop(0)

        return False


# Configuration
KAFKA_BROKER = _required_env("KAFKA_BROKER")
KAFKA_TOPIC = _required_env("KAFKA_TOPIC")
ALERTS_TOPIC = os.getenv("ANOMALY_DETECTOR_OUTPUT_TOPIC", "system.alerts")

INFLUXDB_URL = _required_env("INFLUXDB_URL")
INFLUXDB_TOKEN = _required_env("INFLUXDB_TOKEN")
INFLUXDB_ORG = _required_env("INFLUXDB_ORG")
INFLUXDB_BUCKET = _required_env("INFLUXDB_BUCKET")

def wait_for_kafka(max_attempts=30, wait_seconds=2):
    logger.info(f"Waiting for Kafka at {KAFKA_BROKER}...")
    for attempt in range(1, max_attempts + 1):
        try:
            consumer = KafkaConsumer(
                bootstrap_servers=KAFKA_BROKER,
                request_timeout_ms=5000,
                api_version_auto_timeout_ms=5000,
            )
            consumer.close()
            logger.info(f"✅ Kafka ready on attempt {attempt}!")
            return True
        except NoBrokersAvailable:
            logger.warning(f"   Attempt {attempt}/{max_attempts} - waiting {wait_seconds}s...")
            time.sleep(wait_seconds)
        except Exception as e:
            logger.error(f"   Attempt {attempt}/{max_attempts} - {e}")
            time.sleep(wait_seconds)
    return False

def wait_for_influxdb(max_attempts=30, wait_seconds=2):
    logger.info(f"Waiting for InfluxDB at {INFLUXDB_URL}...")
    for attempt in range(1, max_attempts + 1):
        try:
            client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
            client.ready()
            logger.info(f"✅ InfluxDB ready on attempt {attempt}!")
            return True
        except Exception as e:
            logger.warning(f"   Attempt {attempt}/{max_attempts} - {e}, waiting {wait_seconds}s...")
            time.sleep(wait_seconds)
    return False

def create_consumer():
    return KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BROKER,
        auto_offset_reset='latest',  # Start from latest if no offset
        value_deserializer=lambda v: json.loads(v.decode('utf-8')),
        consumer_timeout_ms=None,    # Do NOT timeout - run forever
        group_id='kafka-influx-consumer',
        session_timeout_ms=30000,
        heartbeat_interval_ms=10000,
    )

def validate_payload(data):
    """Validate required fields in MQTT payload"""
    required_fields = [
        'device_id',
        'timestamp',
        'water_level_cm',
        'temperature',
        'pressure',
        'rainfall_intensity_mmh',
        'flow_velocity_ms',
        'device_status',
    ]
    if not all(k in data for k in required_fields):
        return False
    device_status = data.get('device_status')
    if not isinstance(device_status, dict):
        return False
    if not all(k in device_status for k in ['battery_voltage', 'signal_strength_dbm']):
        return False
    return True


def parse_timestamp(timestamp_value):
    """Convert the incoming timestamp string or numeric value into nanoseconds."""
    if isinstance(timestamp_value, (int, float)):
        return int(timestamp_value)

    if isinstance(timestamp_value, str):
        try:
            parsed = datetime.strptime(timestamp_value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            parsed = datetime.fromisoformat(timestamp_value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp() * 1e9)

    raise ValueError(f"Unsupported timestamp value: {timestamp_value!r}")

def process_message(data, write_api, detector, alert_producer):
    """
    Process Kafka message: validate, check for anomalies, then write to InfluxDB.
    
    Flow:
    1. Validate payload
    2. Check for anomalies using Z-score method
    3. If anomaly: publish alert to system.alerts, skip InfluxDB write
    4. If clean: write to InfluxDB
    """
    try:
        # Validate payload
        if not validate_payload(data):
            logger.warning(f"Skipped invalid payload: {data}")
            return False

        device_id = data['device_id']
        water_level = float(data['water_level_cm'])
        timestamp = parse_timestamp(data['timestamp'])
        device_status = data['device_status']

        # Check for anomalies
        if detector.is_anomaly(device_id, water_level):
            # Publish anomaly alert
            anomaly_event = {
                "event": "anomaly:new",
                "timestamp": int(time.time()),
                "data": {
                    "sensor_id": device_id,
                    "type": "SUDDEN_SPIKE",
                    "severity": "HIGH",
                    "water_level_cm": water_level,
                    "temperature": float(data['temperature']),
                    "pressure": float(data['pressure']),
                    "rainfall_intensity_mmh": float(data['rainfall_intensity_mmh']),
                    "flow_velocity_ms": float(data['flow_velocity_ms']),
                    "device_status": device_status,
                    "description": f"Impossible water level jump detected: {water_level}cm. Data discarded.",
                }
            }
            try:
                alert_producer.send(ALERTS_TOPIC, anomaly_event)
                logger.info(f"[Anomaly Alert] ✅ Published to {ALERTS_TOPIC}: {device_id}")
            except Exception as e:
                logger.error(f"Failed to send anomaly alert: {e}")
            return False  # Do NOT write anomalous data to InfluxDB

        # Data is clean - write to InfluxDB
        point = Point("flood_measurements") \
            .tag("device_id", device_id) \
            .field("water_level_cm", water_level) \
            .field("temperature", float(data['temperature'])) \
            .field("pressure", float(data['pressure'])) \
            .field("rainfall_intensity_mmh", float(data['rainfall_intensity_mmh'])) \
            .field("flow_velocity_ms", float(data['flow_velocity_ms'])) \
            .field("battery_voltage", float(device_status['battery_voltage'])) \
            .field("signal_strength_dbm", float(device_status['signal_strength_dbm'])) \
            .time(timestamp)

        write_api.write(bucket=INFLUXDB_BUCKET, record=point)
        logger.info(
            f"[Kafka→InfluxDB] ✅ {device_id} | Water: {water_level}cm | Temp: {data['temperature']}°C | "
            f"Rain: {data['rainfall_intensity_mmh']}mm/h | Flow: {data['flow_velocity_ms']}m/s"
        )
        return True
    except ValueError as e:
        logger.error(f"Value conversion error: {e} for payload {data}")
        return False
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        return False

def main():
    logger.info("=" * 60)
    logger.info("🌊 KAFKA → INFLUXDB BRIDGE SERVICE (with Anomaly Detection)")
    logger.info(f"   Kafka:     {KAFKA_BROKER}")
    logger.info(f"   Topic:     {KAFKA_TOPIC}")
    logger.info(f"   InfluxDB:  {INFLUXDB_URL}")
    logger.info(f"   Org:       {INFLUXDB_ORG}")
    logger.info(f"   Bucket:    {INFLUXDB_BUCKET}")
    logger.info(f"   Alerts to: {ALERTS_TOPIC}")
    logger.info("=" * 60)

    # Wait for services
    if not wait_for_kafka():
        logger.error("❌ Kafka failed to become ready")
        return 1

    if not wait_for_influxdb():
        logger.error("❌ InfluxDB failed to become ready")
        return 1

    # Initialize clients
    try:
        influx_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
        write_api = influx_client.write_api(write_options=SYNCHRONOUS)
        logger.info("✅ InfluxDB client initialized")
        
        alert_producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            acks='all',
        )
        logger.info("✅ Kafka producer (for alerts) initialized")
    except Exception as e:
        logger.error(f"Failed to initialize clients: {e}")
        return 1

    # Initialize anomaly detector
    detector = AnomalyDetector(history_size=10, z_threshold=3.0)
    logger.info("✅ Anomaly detector initialized")

    retry_count = 0
    max_retries = 10
    
    logger.info("✅ Pipeline started!")
    logger.info("   Kafka → [Anomaly Check] → InfluxDB bridge active...")
    logger.info("-" * 60)

    while True:
        try:
            consumer = create_consumer()
            logger.info("✅ Kafka consumer connected")
            retry_count = 0

            for message in consumer:
                try:
                    data = message.value
                    process_message(data, write_api, detector, alert_producer)
                except KafkaError as e:
                    logger.error(f"Kafka error: {e}")
                except Exception as e:
                    logger.error(f"Message processing error: {e}")

        except NoBrokersAvailable:
            retry_count += 1
            if retry_count > max_retries:
                logger.error(f"❌ Kafka unavailable after {max_retries} retries")
                return 1
            logger.warning(f"Kafka unavailable (retry {retry_count}/{max_retries}), waiting 5s...")
            time.sleep(5)
        except Exception as e:
            retry_count += 1
            if retry_count > max_retries:
                logger.error(f"❌ Fatal error after {max_retries} retries: {e}")
                return 1
            logger.error(f"Consumer error (retry {retry_count}/{max_retries}): {e}")
            time.sleep(5)

if __name__ == "__main__":
    try:
        exit(main())
    except KeyboardInterrupt:
        logger.info("\n👋 Shutting down...")
        exit(0)
