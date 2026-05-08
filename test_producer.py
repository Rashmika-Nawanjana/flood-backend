#!/usr/bin/env python3
from kafka import KafkaProducer
import json
import time

print("Connecting to Kafka...")
producer = KafkaProducer(
    bootstrap_servers='localhost:9093',
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
    acks='all',
)
print("✓ Producer created")

print("Sending test message...")
future = producer.send('flood-sensor-data', {'test': 'message', 'timestamp': str(time.time())})
print("✓ Message sent, waiting for callback...")
try:
    record_metadata = future.get(timeout=10)
    print(f"✓ Confirmed at: {record_metadata.topic}[{record_metadata.partition}] @ offset {record_metadata.offset}")
except Exception as e:
    print(f"✗ Error: {e}")

producer.flush()
print("✓ Flushed")
producer.close()
print("✓ Closed")
