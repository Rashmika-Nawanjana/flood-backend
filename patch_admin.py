with open("app/api/routers/admin.py", "r") as f:
    lines = f.readlines()

new_endpoint = """
class AlertResolutionPayload(BaseModel):
    resolution_note: str = Field(...)

def get_kafka_producer():
    from kafka import KafkaProducer
    import json
    return KafkaProducer(
        bootstrap_servers='localhost:9092',
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

@router.patch("/alerts/{alert_id}")
def update_alert(alert_id: str, payload: AlertResolutionPayload) -> dict:
    # Normally we'd update the DB here first:
    # update = "UPDATE alerts SET status = 'RESOLVED', resolved_at = NOW(), resolution_note = %s WHERE alert_id = %s RETURNING *"
    from datetime import datetime, timezone
    
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    event = {
        "event": "alert:resolved",
        "timestamp": timestamp,
        "data": {
            "alert_id": alert_id,
            "zone_id": "ZONE-K1", # In a real implementation this would come from the DB row
            "resolved_at": timestamp,
            "resolution_note": payload.resolution_note
        }
    }
    
    try:
        producer = get_kafka_producer()
        producer.send("system.alerts", event)
        producer.flush()
    except Exception as e:
        print("Failed to publish alert:resolved", e)
        
    return {"status": "success", "event": "alert:resolved", "data": event["data"]}

"""

# Insert at end of file
lines.append("\n" + new_endpoint)

with open("app/api/routers/admin.py", "w") as f:
    f.write("".join(lines))
    
print("Updated admin.py")
