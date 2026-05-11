import json
import logging
import time

from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import NoBrokersAvailable

from config import KAFKA_BROKER, KAFKA_TOPIC

logger = logging.getLogger(__name__)


def wait_for_kafka(max_attempts: int = 30, wait_seconds: int = 2) -> bool:
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
        except Exception as exc:
            logger.error(f"   Attempt {attempt}/{max_attempts} - {exc}")
            time.sleep(wait_seconds)
    return False


def create_consumer() -> KafkaConsumer:
    return KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BROKER,
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        group_id="kafka-influx-consumer",
        session_timeout_ms=30000,
        heartbeat_interval_ms=10000,
        max_poll_interval_ms=300000,
    )


def create_alert_producer() -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=KAFKA_BROKER,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks="all",
    )
