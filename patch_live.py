--- app/ws/live.py
+++ app/ws/live.py
@@ -1,4 +1,5 @@
 import asyncio
+import json
 from datetime import datetime, timezone
 
 import socketio
@@ -275,10 +276,26 @@
         await asyncio.sleep(12)
 
 
+async def _kafka_consumer_loop() -> None:
+    try:
+        from aiokafka import AIOKafkaConsumer
+        consumer = AIOKafkaConsumer(
+            'analytics.predictions',
+            bootstrap_servers='localhost:9092',
+            value_deserializer=lambda v: json.loads(v.decode('utf-8'))
+        )
+        await consumer.start()
+        async for msg in consumer:
+            payload = msg.value
+            if payload.get("event") == "zone:risk:update":
+                await sio.emit("zone:risk:update", payload)
+    except Exception as e:
+        print("Kafka consumer Error: ", e)
+
 async def _ensure_background_task() -> None:
     global _broadcast_task_started
     async with _task_lock:
         if not _broadcast_task_started:
             sio.start_background_task(_broadcast_loop)
+            sio.start_background_task(_kafka_consumer_loop)
             _broadcast_task_started = True
