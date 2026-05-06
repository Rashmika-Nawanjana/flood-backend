# 🌊 Flood Sensor Data Pipeline

Asynchronous data pipeline that bridges MQTT sensors → Kafka → InfluxDB for time-series storage.

## Architecture

```
MQTT Sensors
     ↓
[mqtt-kafka-service] → Kafka Cluster
                          ↓
                  [kafka-influx-service]
                          ↓
                      InfluxDB
```

## Services

### 1. mqtt-kafka-service
- **Purpose**: Bridge MQTT sensors to Kafka
- **Features**:
  - Subscribes to `MQTT_TOPIC` (default: `flood/sensors/#`)
  - Validates the MQTT telemetry schema before forwarding
  - Batches messages for throughput (16KB batches, 100ms window)
  - Automatic reconnection on MQTT disconnect
  - Thread-safe producer with lock
- **Environment Variables**:
  - `MQTT_BROKER` (default: `mosquitto`)
  - `MQTT_PORT` (default: `1883`)
  - `KAFKA_BROKER` (default: `localhost:9092`)
  - `MQTT_TOPIC` (default: `flood/sensors/#`)
  - `KAFKA_TOPIC` (default: `flood-sensor-data`)

### 2. kafka-influx-service
- **Purpose**: Consume Kafka messages and write to InfluxDB
- **Features**:
  - Consumes from Kafka topic with consumer groups
  - Validates schema before write
  - Runs anomaly detection before persistence
  - Publishes anomaly alerts to Kafka (`system.alerts`)
  - Type conversion with error handling
  - Automatic reconnection on Kafka/InfluxDB failures
  - No consumer timeout (runs indefinitely)
  - Measurement: `flood_measurements`
  - Tags: `device_id`
  - Fields: `water_level_cm`, `temperature`, `pressure`, `rainfall_intensity_mmh`, `flow_velocity_ms`, `battery_voltage`, `signal_strength_dbm`
- **Environment Variables**:
  - `KAFKA_BROKER` (default: `localhost:9092`)
  - `INFLUXDB_URL` (default: `http://localhost:8086`)
  - `INFLUXDB_TOKEN` (required)
  - `INFLUXDB_ORG` (default: `flood`)
  - `INFLUXDB_BUCKET` (default: `telemetry`)

## Running the Pipeline

### Option 1: Docker Compose (Production)

```bash
docker compose up -d zookeeper kafka mqtt-kafka-service kafka-influx-service
```

Services will automatically:
- Wait for dependencies (Kafka, InfluxDB)
- Start consuming/processing messages
- Restart on failure

### Option 2: Local Development

Terminal 1 - Start Kafka & Zookeeper:
```bash
docker compose up zookeeper kafka
```

Terminal 2 - Start MQTT service:
```bash
cd mqtt-kafka-service
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python main.py
```

Terminal 3 - Start InfluxDB service:
```bash
cd kafka-influx-service
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python main.py
```

## Testing the Pipeline

### Send Mock MQTT Message:

```bash
docker exec -it flood-mosquitto sh -lc 'mosquitto_pub -h localhost -t flood/sensors/sensor-1 -m "{\"device_id\":\"NODE_01\",\"timestamp\":\"2026-04-21 14:36:12\",\"temperature\":28.50,\"pressure\":1011.25,\"water_level_cm\":45.32,\"rainfall_intensity_mmh\":12.5,\"flow_velocity_ms\":1.8,\"device_status\":{\"battery_voltage\":3.9,\"signal_strength_dbm\":-68}}"'
```

If you are running the command directly in Windows `cmd`, use double quotes outside the JSON payload and single quotes are not treated as quoting characters.

### Verify InfluxDB Storage:

```bash
docker exec flood-influxdb influx query --org flood --token my-super-secret-token-12345 "from(bucket:\"telemetry\") |> range(start: -1h)"
```

## Message Format

Expected MQTT payload (JSON):
```json
{
  "device_id": "NODE_01",
  "timestamp": "2026-04-21 14:36:12",
  "temperature": 28.5,
  "pressure": 1011.25,
  "water_level_cm": 45.32,
  "rainfall_intensity_mmh": 12.5,
  "flow_velocity_ms": 1.8,
  "device_status": {
    "battery_voltage": 3.9,
    "signal_strength_dbm": -68
  }
}
```

**Required Fields**: `device_id`, `timestamp`, `water_level_cm`, `temperature`, `pressure`, `rainfall_intensity_mmh`, `flow_velocity_ms`, `device_status.battery_voltage`, `device_status.signal_strength_dbm`
**Optional Fields**: none for the current schema

## Error Handling

### mqtt-kafka-service
- Skips invalid JSON or missing required fields
- Logs warnings for dropped messages
- Automatic MQTT reconnection on disconnect

### kafka-influx-service
- Retries Kafka consumer up to 10 times before exiting
- Skips invalid payloads (logs warning)
- Type conversion errors logged but pipeline continues
- Automatic reconnection on broker failure

## Configuration

Edit environment variables in `.env.example` before running:

```bash
# MQTT Configuration
MQTT_BROKER=mosquitto
MQTT_PORT=1883
MQTT_TOPIC=flood/sensors/#

# Kafka Configuration
KAFKA_BROKER=kafka:9092
KAFKA_TOPIC=flood-sensor-data

# InfluxDB Configuration
INFLUXDB_URL=http://influxdb:8086
INFLUXDB_TOKEN=my-token
INFLUXDB_ORG=flood
INFLUXDB_BUCKET=telemetry
```

## Monitoring

### Check service logs:
```bash
docker compose logs -f mqtt-kafka-service
docker compose logs -f kafka-influx-service
```

### Kafka topic messages:
```bash
docker exec flood-kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic flood-sensor-data --from-beginning
```

### InfluxDB data query:
```bash
docker exec flood-influxdb influx query --org flood --token my-super-secret-token-12345 "from(bucket:\"telemetry\") |> range(start: -24h) |> filter(fn:(r) => r._measurement == \"flood_measurements\")"
```

## Performance Tuning

### mqtt-kafka-service
- `batch_size=16384` (16KB): Adjust for throughput vs latency
- `linger_ms=100`: Wait up to 100ms for batch fill

### kafka-influx-service
- Consumer group: `kafka-influx-consumer` (customize per deployment)
- Session timeout: 30s (increase if experiencing rebalancing)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Kafka not ready" | Wait for Zookeeper → Kafka startup (30-60s) |
| "InfluxDB connection failed" | Verify token and bucket exist in InfluxDB |
| "No messages flowing" | Check MQTT broker is accessible, verify device publishes to correct topic |
| "Consumer timeout" *(old version)* | Fixed in v2 - consumer now runs indefinitely |
| "Missing field errors" | Verify MQTT payload contains all required fields |

## Future Enhancements

- [ ] Add Protobuf/Avro schema validation
- [ ] Multi-topic support with routing
- [ ] Dead-letter queue for failed writes
- [ ] Message compression (Snappy/LZ4)
- [ ] Metrics export (Prometheus)
- [ ] Persistent offset tracking
