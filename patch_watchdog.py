import re

with open("app/ws/live.py", "r") as f:
    content = f.read()

watchdog_code = """
_sensor_last_seen = {}

async def _sensor_watchdog_loop() -> None:
    try:
        from kafka import KafkaProducer
        import json
        
        # Non async producer for the watchdog thread
        def get_producer():
            return KafkaProducer(
                bootstrap_servers='localhost:9092',
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            
        while True:
            await asyncio.sleep(60) # check every minute
            now = datetime.now(timezone.utc)
            offline_sensors = []
            
            for sensor_id, last_seen_time in list(_sensor_last_seen.items()):
                # If more than 5 minutes elapsed
                if (now - last_seen_time).total_seconds() > 300:
                    offline_sensors.append((sensor_id, last_seen_time))
            
            if offline_sensors:
                producer = get_producer()
                for sensor_id, last_seen_time in offline_sensors:
                    event = {
                        "event": "sensor:offline",
                        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "data": {
                            "sensor_id": sensor_id,
                            "zone_id": "ZONE-K1", # Mocked zone map
                            "last_seen": last_seen_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "status": "OFFLINE"
                        }
                    }
                    producer.send("system.alerts", event)
                    # Stop tracking it so we don't spam offline events
                    del _sensor_last_seen[sensor_id]
                producer.flush()
    except Exception as e:
        print("Sensor watchdog error:", e)

"""

# find start of _kafka_sensor_consumer_loop
idx = content.find("async def _kafka_sensor_consumer_loop")
content = content[:idx] + watchdog_code + "\n" + content[idx:]

# inject last_seen tracking
track_code = """
            if "device_id" in raw_data:
                _sensor_last_seen[raw_data["device_id"]] = datetime.now(timezone.utc)
"""
content = content.replace('if "device_id" in raw_data:', track_code.strip())

# Add it to the background task runner
content = content.replace("sio.start_background_task(_kafka_sensor_consumer_loop)", "sio.start_background_task(_kafka_sensor_consumer_loop)\n            sio.start_background_task(_sensor_watchdog_loop)")

# Also listen for sensor:offline in alerts consumer
content = content.replace('["alert:new", "alert:resolved", "anomaly:new"]', '["alert:new", "alert:resolved", "anomaly:new", "sensor:offline"]')

with open("app/ws/live.py", "w") as f:
    f.write(content)

print("Injected watchdog")
