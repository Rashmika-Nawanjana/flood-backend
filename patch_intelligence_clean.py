with open('intelligence-service/app/api/routers/intelligence.py', 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.startswith("def get_kafka_producer():"):
        break
    if "import json" in line or "from datetime import datetime, timezone" in line or "from kafka import KafkaProducer" in line:
        continue
    new_lines.append(line)

with open('intelligence-service/app/api/routers/intelligence.py', 'w') as f:
    f.write("".join(new_lines))
    print("Cleaned!")
