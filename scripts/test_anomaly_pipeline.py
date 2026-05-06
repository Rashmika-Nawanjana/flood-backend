#!/usr/bin/env python3
"""
Publish test telemetry to Kafka to trigger anomaly detection, then read alerts
from Kafka and (optionally) anomalies from Postgres.

Usage:
  python scripts/test_anomaly_pipeline.py
  python scripts/test_anomaly_pipeline.py --device-id NODE_01 --spike 220
"""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
from dotenv import load_dotenv
from kafka import KafkaConsumer, KafkaProducer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test anomaly detection pipeline.")
    parser.add_argument("--device-id", default="NODE_01")
    parser.add_argument("--normal", type=int, default=6, help="Normal data points before spike")
    parser.add_argument("--spike", type=float, default=220.0, help="Spike water level (cm)")
    parser.add_argument("--interval", type=int, default=5, help="Seconds between samples")
    parser.add_argument("--wait-alert", type=int, default=15, help="Seconds to wait for alert")
    return parser.parse_args()


def build_payload(device_id: str, timestamp: datetime, water_level_cm: float) -> dict:
    return {
        "device_id": device_id,
        "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "temperature": 28.5,
        "pressure": 1011.25,
        "water_level_cm": water_level_cm,
        "rainfall_intensity_mmh": 12.5,
        "flow_velocity_ms": 1.8,
        "device_status": {
            "battery_voltage": 3.9,
            "signal_strength_dbm": -68,
        },
    }


def main() -> int:
    load_dotenv()
    args = parse_args()

    kafka_broker = os.getenv("KAFKA_BROKER", "localhost:9093")
    if kafka_broker in {"localhost:9092", "127.0.0.1:9092"}:
        print("[info] KAFKA_BROKER points to host 9092; using localhost:9093 for external client access.")
        kafka_broker = "localhost:9093"
    kafka_topic = os.getenv("KAFKA_TOPIC", "flood-sensor-data")
    alerts_topic = os.getenv("ANOMALY_DETECTOR_OUTPUT_TOPIC", "system.alerts")
    database_url = os.getenv("DATABASE_URL")
    if database_url and database_url.startswith("postgresql+psycopg://"):
        database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    producer = KafkaProducer(
        bootstrap_servers=kafka_broker,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks="all",
        max_block_ms=15000,
    )

    now = datetime.now(timezone.utc)
    print("=" * 80)
    print("Publishing normal telemetry...")
    for i in range(args.normal):
        print(f"  Preparing message {i+1}...", end=" ", flush=True)
        payload = build_payload(args.device_id, now + timedelta(seconds=i * args.interval), 40 + i * 0.5)
        try:
            future = producer.send(kafka_topic, payload)
            future.get(timeout=10)
            print(f"  ✓ sent normal {i + 1}/{args.normal}: water_level_cm={payload['water_level_cm']}")
        except Exception as e:
            print(f"  ✗ Error sending message {i+1}: {e}")
            return 1
        time.sleep(0.2)

    spike_payload = build_payload(args.device_id, now + timedelta(seconds=args.normal * args.interval), args.spike)
    try:
        future = producer.send(kafka_topic, spike_payload)
        future.get(timeout=10)
        print(f"  ✓ sent spike: water_level_cm={spike_payload['water_level_cm']}")
    except Exception as e:
        print(f"  ✗ Error sending spike: {e}")
        return 1
    producer.flush()
    producer.close()
    print(f"✓ Published {args.normal + 1} messages total")

    print("=" * 80)
    print(f"Waiting up to {args.wait_alert}s for anomaly alert on {alerts_topic}...")
    group_id = f"anomaly-test-{uuid.uuid4().hex[:8]}"
    consumer = KafkaConsumer(
        alerts_topic,
        bootstrap_servers=kafka_broker,
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        consumer_timeout_ms=args.wait_alert * 1000,
        group_id=group_id,
    )

    alert_received = False
    for msg in consumer:
        alert_received = True
        print("✓ ALERT RECEIVED:")
        print(json.dumps(msg.value, indent=2))
        break

    consumer.close()
    if not alert_received:
        print("✗ No alert received (check kafka-influx-service logs and detector thresholds).")
        return 1

    if database_url:
        print("=" * 80)
        print("Checking anomalies table in Postgres...")
        try:
            with psycopg.connect(database_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT anomaly_id, sensor_id, detected_at, type, severity, anomaly_score "
                        "FROM anomalies ORDER BY detected_at DESC LIMIT 5"
                    )
                    rows = cur.fetchall()
            if not rows:
                print("No anomaly rows found yet.")
            for row in rows:
                print(row)
        except Exception as exc:
            print(f"Failed to query anomalies: {exc}")
    else:
        print("DATABASE_URL not set; skipping Postgres check.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
