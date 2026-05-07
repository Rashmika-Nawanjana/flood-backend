import logging
import time

from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

from config import INFLUXDB_BUCKET, INFLUXDB_ORG, INFLUXDB_TOKEN, INFLUXDB_URL

logger = logging.getLogger(__name__)


def wait_for_influxdb(max_attempts: int = 30, wait_seconds: int = 2) -> bool:
    logger.info(f"Waiting for InfluxDB at {INFLUXDB_URL}...")
    for attempt in range(1, max_attempts + 1):
        try:
            client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
            client.ready()
            logger.info(f"✅ InfluxDB ready on attempt {attempt}!")
            return True
        except Exception as exc:
            logger.warning(f"   Attempt {attempt}/{max_attempts} - {exc}, waiting {wait_seconds}s...")
            time.sleep(wait_seconds)
    return False


def create_influx_client() -> InfluxDBClient:
    return InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)


def create_write_api(client: InfluxDBClient):
    return client.write_api(write_options=SYNCHRONOUS)


def get_bucket() -> str:
    return INFLUXDB_BUCKET
