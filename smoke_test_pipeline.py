#!/usr/bin/env python3
"""
Smoke test for MQTT→Kafka→InfluxDB pipeline
Publishes test sensor data to Kafka and verifies it reaches InfluxDB
"""
import json
import time
import logging
import os
from kafka import KafkaProducer
from influxdb_client import InfluxDBClient
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Configuration
KAFKA_BROKER = "localhost:9093"  # Use the PLAINTEXT_HOST listener
KAFKA_TOPIC = "flood-sensor-data"
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "my-super-secret-token-12345")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "flood")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "telemetry")

def test_kafka_producer():
    """Test publishing to Kafka"""
    logger.info("=" * 60)
    logger.info("STEP 1: Publishing test messages to Kafka")
    logger.info("=" * 60)
    
    try:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            api_version=(0, 10, 0),  # Explicitly set API version
        )
        
        # Test message 1: Water level sensor
        # Format expected by kafka-influx-service
        test_msg_1 = {
            "device_id": "MR-KND-101",
            "water_level_cm": 250.0,  # 2.5 meters
            "temperature": 22.5,       # Celsius
            "pressure": 1013.25        # hPa
        }
        
        # Test message 2: Another device
        test_msg_2 = {
            "device_id": "SENSOR-TEST-002",
            "water_level_cm": 180.5,
            "temperature": 23.1,
            "pressure": 1013.30
        }
        
        logger.info(f"Publishing message 1: {test_msg_1}")
        future1 = producer.send(KAFKA_TOPIC, value=test_msg_1)
        future1.get(timeout=10)
        logger.info("✓ Message 1 published successfully")
        
        time.sleep(1)
        
        logger.info(f"Publishing message 2: {test_msg_2}")
        future2 = producer.send(KAFKA_TOPIC, value=test_msg_2)
        future2.get(timeout=10)
        logger.info("✓ Message 2 published successfully")
        
        producer.close()
        logger.info("✓ Kafka producer test PASSED\n")
        return True
        
    except Exception as e:
        logger.error(f"✗ Kafka publisher failed: {e}\n")
        return False

def test_influxdb_data():
    """Test if data reached InfluxDB"""
    logger.info("=" * 60)
    logger.info("STEP 2: Waiting for Kafka→InfluxDB bridge to process messages")
    logger.info("=" * 60)
    
    time.sleep(3)  # Give kafka-influx-service time to consume and write
    
    try:
        client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
        query_api = client.query_api()
        
        logger.info("Querying InfluxDB for written data...")
        
        # Query for all records in the bucket from the last 10 minutes
        query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: -10m)
        '''
        
        logger.info(f"Executing query...\n")
        tables = query_api.query(query)
        
        records_found = 0
        devices = set()
        for table in tables:
            for record in table.records:
                records_found += 1
                device_id = record.values.get('device_id', 'N/A')
                field_name = record.values.get('_field', 'N/A')
                field_value = record.values.get('_value', 'N/A')
                devices.add(device_id)
                if records_found <= 6:  # Show first few records
                    logger.info(f"  Record {records_found}: device={device_id} | {field_name}={field_value}")
        
        client.close()
        
        if records_found > 0:
            logger.info(f"\n✓ InfluxDB test PASSED: Found {records_found} total records from {len(devices)} devices\n")
            return True
        else:
            logger.warning("✗ No records found in InfluxDB\n")
            return False
            
    except Exception as e:
        logger.error(f"✗ InfluxDB query failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False

def main():
    logger.info("\n" + "=" * 60)
    logger.info("MQTT→KAFKA→INFLUXDB PIPELINE SMOKE TEST")
    logger.info("=" * 60 + "\n")
    
    # Test 1: Kafka producer
    kafka_ok = test_kafka_producer()
    
    # Test 2: InfluxDB data arrival
    influx_ok = test_influxdb_data()
    
    # Summary
    logger.info("=" * 60)
    logger.info("SMOKE TEST SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Kafka Producer:     {'✓ PASS' if kafka_ok else '✗ FAIL'}")
    logger.info(f"InfluxDB Data:      {'✓ PASS' if influx_ok else '✗ FAIL'}")
    logger.info(f"Overall:            {'✓ PASS' if (kafka_ok and influx_ok) else '⚠ PARTIAL'}")
    logger.info("=" * 60 + "\n")
    
    return 0 if (kafka_ok and influx_ok) else 1

if __name__ == "__main__":
    exit(main())
