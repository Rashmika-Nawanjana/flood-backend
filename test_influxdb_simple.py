#!/usr/bin/env python3
"""
Simple InfluxDB query test
"""
import logging
import os
from influxdb_client import InfluxDBClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "my-super-secret-token-12345")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "flood")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "telemetry")

try:
    client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
    
    # Query without profiler
    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: -10m)
    '''
    
    logger.info(f"Running query:\n{query}\n")
    query_api = client.query_api()
    tables = query_api.query(query)
    
    record_count = 0
    for table in tables:
        logger.info(f"Table with {len(table.records)} records from: {table.records[0].get_measurement() if table.records else 'N/A'}")
        for record in table.records:
            record_count += 1
            logger.info(f"  Record {record_count}: {record.values}")
    
    logger.info(f"\nTotal records found: {record_count}")
    client.close()
    
except Exception as e:
    logger.error(f"Error: {e}")
    import traceback
    traceback.print_exc()
