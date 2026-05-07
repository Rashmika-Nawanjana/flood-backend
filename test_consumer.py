#!/usr/bin/env python3
from kafka import KafkaConsumer
import json
import uuid

print("Creating consumer...")
group_id = f"test-{uuid.uuid4().hex[:8]}"
print(f"Group ID: {group_id}")

consumer = KafkaConsumer(
    'system.alerts',
    bootstrap_servers='localhost:9093',
    auto_offset_reset='earliest',
    value_deserializer=lambda v: json.loads(v.decode('utf-8')),
    consumer_timeout_ms=5000,
    group_id=group_id,
)
print("✓ Consumer created and subscribed")

print("Waiting for messages (5s timeout)...")
messages_count = 0
for msg in consumer:
    print(f"✓ Got message: {msg.value}")
    messages_count += 1
    if messages_count >= 1:
        break

if messages_count == 0:
    print("✗ No messages received (timeout)")
else:
    print(f"✓ Received {messages_count} messages")

consumer.close()
print("✓ Closed")
