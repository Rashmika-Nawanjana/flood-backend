import os
import json
import time
import logging
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable, KafkaError
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


# Configuration
KAFKA_BROKER = _required_env("KAFKA_BROKER")
KAFKA_TOPIC = _required_env("KAFKA_TOPIC")

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
    required_fields = ['device_id', 'water_level_cm', 'temperature', 'pressure']
    if not all(k in data for k in required_fields):
        return False
    return True

def process_message(data, write_api):
    """Convert Kafka message to InfluxDB point"""
    try:
        # Validate payload
        if not validate_payload(data):
            logger.warning(f"Skipped invalid payload: {data}")
            return False

        # Use provided timestamp or current time (in nanoseconds)
        timestamp = data.get('timestamp', int(time.time() * 1e9))

        # Create InfluxDB point
        point = Point("flood_measurements") \
            .tag("device_id", data['device_id']) \
            .field("water_level_cm", float(data['water_level_cm'])) \
            .field("temperature", float(data['temperature'])) \
            .field("pressure", float(data['pressure'])) \
            .time(timestamp)

        # Write to InfluxDB
        write_api.write(bucket=INFLUXDB_BUCKET, record=point)
        logger.info(f"[Kafka→InfluxDB] ✅ {data['device_id']} | Water: {data['water_level_cm']}cm | Temp: {data['temperature']}°C")
        return True
    except ValueError as e:
        logger.error(f"Value conversion error: {e} for payload {data}")
        return False
    except Exception as e:
        logger.error(f"Error writing to InfluxDB: {e}")
        return False

def main():
    logger.info("=" * 60)
    logger.info("🌊 KAFKA → INFLUXDB BRIDGE SERVICE")
    logger.info(f"   Kafka:     {KAFKA_BROKER}")
    logger.info(f"   InfluxDB:  {INFLUXDB_URL}")
    logger.info(f"   Org:       {INFLUXDB_ORG}")
    logger.info(f"   Bucket:    {INFLUXDB_BUCKET}")
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
    except Exception as e:
        logger.error(f"Failed to initialize InfluxDB client: {e}")
        return 1

    retry_count = 0
    max_retries = 10
    
    logger.info("✅ Pipeline started!")
    logger.info("   Kafka → InfluxDB bridge active...")
    logger.info("-" * 60)

    while True:
        try:
            consumer = create_consumer()
            logger.info("✅ Kafka consumer connected")
            retry_count = 0

            for message in consumer:
                try:
                    data = message.value
                    process_message(data, write_api)
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
