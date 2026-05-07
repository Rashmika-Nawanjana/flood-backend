from kafka import KafkaProducer
import json
import time

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

event = {
    "event": "zone:risk:update",
    "timestamp": "2026-05-07T12:00:00Z",
    "data": {
        "zone_id": "ZONE-K1",
        "zone_name": "Getambe Basin",
        "previous_level": "WARNING",
        "current_level": "HIGH",
        "risk_score": 85.0,
        "color_code": "#FF0000"
    }
}

print("Sending message to analytics.predictions...")
producer.send('analytics.predictions', event)
producer.flush()
print("Sent successfully.")
