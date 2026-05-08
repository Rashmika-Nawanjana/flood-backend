import json
import logging
import time
import threading
from datetime import datetime, timezone

from kafka import KafkaProducer
from kafka.errors import KafkaError, NoBrokersAvailable
from influxdb_client import Point

from anomaly import AnomalyDetector
from config import ALERTS_TOPIC, INFLUXDB_ORG, INFLUXDB_URL, KAFKA_BROKER, KAFKA_TOPIC, TELEMETRY_TOPIC, DIAGNOSTICS_TOPIC, INFLUXDB_BUCKET
from db import save_anomaly_to_db
from influx_client import create_influx_client, create_write_api, get_bucket, wait_for_influxdb
from kafka_client import create_alert_producer, create_consumer, wait_for_kafka
from schema import parse_timestamp, validate_payload

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def get_sensor_trend(device_id: str, influx_client) -> str:
    """
    Query InfluxDB to get trend by comparing last 2 water level readings.
    Returns: "RISING", "FALLING", "STABLE", or "UNKNOWN"
    """
    try:
        query_api = influx_client.query_api()
        flux = f"""
        from(bucket: "{INFLUXDB_BUCKET}")
          |> range(start: -1h)
          |> filter(fn: (r) => r._measurement == "flood_measurements" and r.device_id == "{device_id}" and r._field == "water_level_cm")
          |> sort(columns: ["_time"], desc: true)
          |> limit(n: 2)
        """
        tables = query_api.query(flux, org=INFLUXDB_ORG)
        
        if not tables or len(tables) == 0:
            return "UNKNOWN"
        
        records = tables[0].records
        if len(records) < 2:
            return "UNKNOWN"
        
        # records[0] is latest (due to desc sort), records[1] is older
        latest_value = records[0].value
        previous_value = records[1].value
        
        if latest_value is None or previous_value is None:
            return "UNKNOWN"
        
        latest = float(latest_value)
        previous = float(previous_value)
        
        threshold = 1.0  # threshold of 1cm to consider as change
        difference = latest - previous
        
        if difference > threshold:
            return "RISING"
        elif difference < -threshold:
            return "FALLING"
        else:
            return "STABLE"
    except Exception as e:
        logger.warning(f"Failed to calculate trend for {device_id}: {e}")
        return "UNKNOWN"

def process_message(data, write_api, detector, alert_producer, influx_client):
    """
    Process Kafka message: validate, check for anomalies, then write to InfluxDB.
    
    Flow:
    1. Validate payload
    2. Check for anomalies using Z-score method
    3. If anomaly: publish alert to system.diagnostics, skip InfluxDB write
    4. If clean: write to InfluxDB and publish telemetry event with calculated trend
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
        is_anomaly, z_score = detector.is_anomaly(device_id, water_level)
        if is_anomaly:
            # Publish anomaly alert
            anomaly_event = {
                "event": "anomaly:new",
                "timestamp": int(time.time()),
                "data": {
                    "sensor_id": device_id,
                    "type": "SUDDEN_SPIKE",
                    "severity": "HIGH",
                    "anomaly_score": z_score,
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
                # send anomaly to diagnostics topic
                alert_producer.send(DIAGNOSTICS_TOPIC, anomaly_event)
                logger.info(f"[Anomaly Alert] ✅ Published to {DIAGNOSTICS_TOPIC}: {device_id}")
            except Exception as e:
                logger.error(f"Failed to send anomaly alert: {e}")

            save_anomaly_to_db(
                data=data,
                anomaly_type=anomaly_event["data"]["type"],
                severity=anomaly_event["data"]["severity"],
                anomaly_score=z_score,
            )
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

        write_api.write(bucket=get_bucket(), record=point)
        logger.info(
            f"[Kafka→InfluxDB] ✅ {device_id} | Water: {water_level}cm | Temp: {data['temperature']}°C | "
            f"Rain: {data['rainfall_intensity_mmh']}mm/h | Flow: {data['flow_velocity_ms']}m/s"
        )
        # Publish cleaned telemetry to telemetry.live for downstream consumers
        try:
            trend = get_sensor_trend(device_id, influx_client)
            telemetry_payload = {
                "event": "sensor:update",
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "data": {
                    "sensor_id": device_id,
                    "zone_id": data.get("zone_id") or None,
                    "current_reading": {
                        "water_level_m": round(water_level / 100.0, 3),
                        "flow_velocity_mps": float(data.get('flow_velocity_ms', 0.0)),
                        "rainfall_mm_per_hr": float(data.get('rainfall_intensity_mmh', 0.0)),
                        "temperature_c": float(data.get('temperature', 0.0)),
                        "air_pressure_hpa": float(data.get('pressure', 0.0)),
                        "trend": trend,
                    },
                },
            }
            # Use a producer created in main
            main_state = globals().get('_kif_state')
            if main_state and 'telemetry_producer' in main_state:
                main_state['telemetry_producer'].send(TELEMETRY_TOPIC, telemetry_payload)
            logger.debug(f"Published cleaned telemetry to {TELEMETRY_TOPIC}: {device_id} (trend: {trend})")
            # record last seen for watchdog
            if main_state is not None:
                last_seen = main_state.setdefault('_sensor_last_seen', {})
                last_seen[device_id] = datetime.now(timezone.utc)
        except Exception as e:
            logger.warning(f"Failed to publish cleaned telemetry: {e}")
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
    logger.info(f"   Bucket:    {get_bucket()}")
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
        influx_client = create_influx_client()
        write_api = create_write_api(influx_client)
        logger.info("✅ InfluxDB client initialized")
        
        alert_producer = create_alert_producer()
        logger.info("✅ Kafka producer (for alerts) initialized")

        # create producers for telemetry and diagnostics
        telemetry_producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            acks='all',
        )
        diagnostics_producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            acks='all',
        )
        # attach to main state for access in process_message
        globals()['_kif_state'] = {
            'telemetry_producer': telemetry_producer,
            'diagnostics_producer': diagnostics_producer,
            '_sensor_last_seen': {},
        }
        logger.info("✅ Kafka producers (telemetry, diagnostics) initialized")
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
                    process_message(data, write_api, detector, alert_producer, influx_client)
                except KafkaError as e:
                    logger.error(f"Kafka error: {e}")
                except Exception as e:
                    logger.error(f"Message processing error: {e}")

        except Exception as e:
            retry_count += 1
            if retry_count > max_retries:
                logger.error(f"❌ Fatal error after {max_retries} retries: {e}")
                return 1
            logger.error(f"Consumer error (retry {retry_count}/{max_retries}): {e}")
            time.sleep(5)

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
