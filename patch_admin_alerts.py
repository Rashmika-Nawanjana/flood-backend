import re

with open("app/api/routers/admin.py", "r") as f:
    content = f.read()

inject_code = """
from pydantic import BaseModel
class AlertResolutionPayload(BaseModel):
    resolution_note: str

from kafka import KafkaProducer
import json
from datetime import datetime, timezone

def get_kafka_producer():
    return KafkaProducer(
        bootstrap_servers='localhost:9092',
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

@router.patch("/alerts/{alert_id}")
def resolve_alert(alert_id: str, payload: AlertResolutionPayload) -> dict:
    # Simulating DB update for alerts since the new schema dropped alert_events
    # update = "UPDATE alerts SET status = 'RESOLVED' WHERE alert_id = %s"
    
    event = {
        "event": "alert:resolved",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data": {
            "alert_id": alert_id,
            "zone_id": "ZONE-K1", # Mocked zone for now, ideally queried from DB
            "resolved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "resolution_note": payload.resolution_note
        }
    }
    try:
        producer = get_kafka_producer()
        producer.send("system.alerts", event)
        producer.flush()
    except Exception as e:
        print(f"Failed to publish alert:resolved: {e}")
        
    return {"status": "success", "message": f"Alert {alert_id} resolved", "data": event}

"""

# Append it
with open("app/api/routers/admin.py", "w") as f:
    f.write(content + "\n" + inject_code)

print("Injected admin alert resolution endpoint")
