import json
from datetime import datetime, timezone
from typing import Dict, Any
from confluent_kafka import Producer
import os

class FloodEventProducer:
    def __init__(self, bootstrap_servers: str = None):
        if not bootstrap_servers:
            bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
            
        self.producer = Producer({
            'bootstrap.servers': bootstrap_servers,
            'client.id': 'flood-backend-producer',
            'linger.ms': 10,
            'retries': 3
        })

    def delivery_report(self, err, msg):
        """Called once for each message produced to indicate delivery result."""
        if err is not None:
            print(f"Message delivery failed: {err}")
        else:
            print(f"Message delivered to {msg.topic()} [{msg.partition()}]")

    def publish_event(self, topic: str, event_name: str, data_payload: Dict[str, Any]):
        """
        Wraps the payload in the standard contract and publishes to Kafka.
        """
        payload = {
            "event": event_name,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "data": data_payload
        }
        
        try:
            self.producer.produce(
                topic=topic,
                value=json.dumps(payload).encode('utf-8'),
                callback=self.delivery_report
            )
            self.producer.poll(0)  # Serve delivery callbacks
        except BufferError:
            print(f"Local producer queue is full ({len(self.producer)} messages awaiting delivery)")
        except Exception as e:
            print(f"Failed to publish to {topic}: {e}")

    def flush(self):
        """Wait for any outstanding messages to be delivered and delivery report callbacks to be triggered."""
        self.producer.flush()


if __name__ == "__main__":
    producer = FloodEventProducer()

    # Simulate Event 1: Sensor Update
    sensor_data = {
        "sensor_id": "MR-KND-001",
        "zone_id": "ZONE-K1",
        "current_reading": {
            "water_level_m": 4.58,
            "flow_velocity_mps": 0.88,
            "rainfall_mm_per_hr": 12.0,
            "temperature_c": 28.5,
            "air_pressure_hpa": 1011.2,
            "trend": "RISING"
        }
    }
    producer.publish_event("telemetry.live", "sensor:update", sensor_data)

    # Simulate Event 7: Anomaly Detected
    anomaly_data = {
        "anomaly_id": "ANM-KND-042",
        "sensor_id": "MR-KND-001",
        "type": "SUDDEN_SPIKE",
        "severity": "HIGH",
        "anomaly_score": 0.94,
        "description": "Unnatural water level spike detected. Data discarded from ML pipeline."
    }
    producer.publish_event("system.diagnostics", "anomaly:new", anomaly_data)

    producer.flush()
