import os


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


KAFKA_BROKER = required_env("KAFKA_BROKER")
KAFKA_TOPIC = required_env("KAFKA_TOPIC")
ALERTS_TOPIC = os.getenv("ANOMALY_DETECTOR_OUTPUT_TOPIC", "system.alerts")
DATABASE_URL = os.getenv("DATABASE_URL")

INFLUXDB_URL = required_env("INFLUXDB_URL")
INFLUXDB_TOKEN = required_env("INFLUXDB_TOKEN")
INFLUXDB_ORG = required_env("INFLUXDB_ORG")
INFLUXDB_BUCKET = required_env("INFLUXDB_BUCKET")
