#!/usr/bin/env python3
"""
Read and display recent telemetry from InfluxDB.

Example:
    python scripts/extract_influx_data.py --range 15m
    python scripts/extract_influx_data.py --bucket telemetry --measurement flood_measurements
"""

from __future__ import annotations

import argparse
import json
import os
import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query and print InfluxDB telemetry.")
    parser.add_argument("--url", default=os.getenv("INFLUXDB_URL", "http://localhost:8086"))
    parser.add_argument("--token", default=os.getenv("INFLUXDB_TOKEN", "my-super-secret-token-12345"))
    parser.add_argument("--org", default=os.getenv("INFLUXDB_ORG", "flood"))
    parser.add_argument("--bucket", default=os.getenv("INFLUXDB_BUCKET", "telemetry"))
    parser.add_argument("--measurement", default="flood_measurements")
    parser.add_argument("--range", dest="time_range", default="1h", help="Flux range window, e.g. 15m, 1h, 24h")
    parser.add_argument("--limit", type=int, default=50, help="Maximum number of records to print")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Print grouped JSON output")
    parser.add_argument("--fields", default=None, help="Comma-separated field list to query")
    parser.add_argument("--adapter-output", default=None, help="Write adapter-ready JSON/NDJSON to a file")
    parser.add_argument(
        "--adapter-format",
        choices=["json", "ndjson"],
        default="json",
        help="Output format for --adapter-output",
    )
    parser.add_argument("--seed", type=int, default=0, help="Insert N demo points before querying")
    parser.add_argument("--device-id", default="NODE_01", help="Device ID used for seeding")
    parser.add_argument("--seed-interval", type=int, default=60, help="Seconds between seeded points")
    return parser.parse_args()


def format_time(value) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, datetime):
        dt = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    return str(value)


def format_timestamp(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def build_point(measurement: str, device_id: str, timestamp: datetime, base: dict) -> Point:
    return (
        Point(measurement)
        .tag("device_id", device_id)
        .field("water_level_cm", base["water_level_cm"])
        .field("temperature", base["temperature"])
        .field("pressure", base["pressure"])
        .field("rainfall_intensity_mmh", base["rainfall_intensity_mmh"])
        .field("flow_velocity_ms", base["flow_velocity_ms"])
        .field("battery_voltage", base["battery_voltage"])
        .field("signal_strength_dbm", base["signal_strength_dbm"])
        .time(timestamp)
    )


def seed_points(client: InfluxDBClient, args: argparse.Namespace) -> None:
    now = datetime.now(timezone.utc)
    base = {
        "water_level_cm": 45.0,
        "temperature": 28.0,
        "pressure": 1011.0,
        "rainfall_intensity_mmh": 10.0,
        "flow_velocity_ms": 1.5,
        "battery_voltage": 3.9,
        "signal_strength_dbm": -70,
    }
    points = []
    for i in range(args.seed):
        jitter = {
            "water_level_cm": base["water_level_cm"] + random.uniform(-1.0, 1.5) + i * 0.4,
            "temperature": base["temperature"] + random.uniform(-0.6, 0.6),
            "pressure": base["pressure"] + random.uniform(-1.2, 1.2),
            "rainfall_intensity_mmh": max(0.0, base["rainfall_intensity_mmh"] + random.uniform(-1.0, 2.0)),
            "flow_velocity_ms": max(0.0, base["flow_velocity_ms"] + random.uniform(-0.3, 0.4)),
            "battery_voltage": base["battery_voltage"] + random.uniform(-0.05, 0.05),
            "signal_strength_dbm": int(round(base["signal_strength_dbm"] + random.uniform(-3, 3))),
        }
        timestamp = now - timedelta(seconds=args.seed_interval * (args.seed - 1 - i))
        points.append(build_point(args.measurement, args.device_id, timestamp, jitter))

    write_api = client.write_api(write_options=SYNCHRONOUS)
    write_api.write(bucket=args.bucket, record=points)


def parse_fields(value: str | None) -> list[str] | None:
    if not value:
        return None
    fields = [item.strip() for item in value.split(",") if item.strip()]
    return fields or None


def build_adapter_records(records, field_filter=None):
    grouped = {}

    for record in records:
        values = record.values
        device_id = values.get("device_id") or values.get("sensor_id")
        if not device_id:
            continue

        timestamp = format_timestamp(record.get_time())
        if not timestamp:
            continue

        field = values.get("_field")
        if not field:
            continue
        if field_filter and field not in field_filter:
            continue

        key = (timestamp, device_id)
        entry = grouped.get(key)
        if entry is None:
            entry = {"device_id": device_id, "timestamp": timestamp}
            grouped[key] = entry

        entry[field] = values.get("_value")

    return [
        grouped[key]
        for key in sorted(grouped.keys(), key=lambda item: (item[0], item[1]))
    ]


def main() -> int:
    args = parse_args()

    fields = parse_fields(args.fields)
    query_lines = [
        f'from(bucket: "{args.bucket}")',
        f'    |> range(start: -{args.time_range})',
        f'    |> filter(fn: (r) => r._measurement == "{args.measurement}")',
    ]
    if fields:
        field_filter = " or ".join([f'r._field == "{field}"' for field in fields])
        query_lines.append(f"    |> filter(fn: (r) => {field_filter})")
    query_lines.append('    |> sort(columns: ["_time"])')
    query = "\n".join(query_lines)

    print("=" * 90)
    print("InfluxDB Extraction Script")
    print("=" * 90)
    print(f"URL        : {args.url}")
    print(f"Org        : {args.org}")
    print(f"Bucket     : {args.bucket}")
    print(f"Measurement: {args.measurement}")
    print(f"Range      : last {args.time_range}")
    print(f"Limit      : {args.limit}")
    if fields:
        print(f"Fields     : {', '.join(fields)}")
    print("=" * 90)
    print("Flux query:")
    print(query.strip())
    print("=" * 90)

    client = None
    try:
        client = InfluxDBClient(url=args.url, token=args.token, org=args.org)
        if args.seed > 0:
            seed_points(client, args)
        tables = client.query_api().query(query)

        records = []
        for table in tables:
            records.extend(table.records)

        if not records:
            print("No records found.")
            return 0

        if args.adapter_output:
            adapter_records = build_adapter_records(records, field_filter=fields)
            output_path = Path(args.adapter_output)
            if args.adapter_format == "ndjson":
                content = "\n".join(json.dumps(entry) for entry in adapter_records)
            else:
                content = json.dumps(adapter_records, indent=2)
            output_path.write_text(content, encoding="utf-8")
            print(f"Adapter output: wrote {len(adapter_records)} records to {output_path}")

        grouped = defaultdict(list)
        for record in records[: args.limit]:
            values = record.values
            device_id = values.get("device_id", values.get("sensor_id", "N/A"))
            grouped[(record.get_time(), device_id)].append(record)

        printed = 0
        if args.json_output:
            output = []
            for (timestamp, device_id) in sorted(grouped.keys()):
                entry = {
                    "time": format_time(timestamp),
                    "device_id": device_id,
                }
                for record in grouped[(timestamp, device_id)]:
                    values = record.values
                    field = values.get("_field", "N/A")
                    entry[field] = values.get("_value", "N/A")
                output.append(entry)
            print(json.dumps(output, indent=2))
        else:
            for (timestamp, device_id) in sorted(grouped.keys()):
                print(f"\nTime: {format_time(timestamp)} Device: {device_id}")
                for record in grouped[(timestamp, device_id)]:
                    printed += 1
                    values = record.values
                    field = values.get("_field", "N/A")
                    measurement = values.get("_measurement", "N/A")
                    value = values.get("_value", "N/A")
                    print(f"  #{printed:03d} measurement={measurement} device_id={device_id} field={field} value={value}")

                    extra_fields = [
                        key for key in [
                            "temperature",
                            "pressure",
                            "water_level_cm",
                            "rainfall_intensity_mmh",
                            "flow_velocity_ms",
                            "battery_voltage",
                            "signal_strength_dbm",
                        ]
                        if key in values
                    ]
                    if extra_fields:
                        extras = ", ".join(f"{key}={values[key]}" for key in extra_fields)
                        print(f"       extras: {extras}")

        print("\n" + "=" * 90)
        print(f"Total printed: {min(len(records), args.limit)} / {len(records)} records")
        print("=" * 90)
        return 0

    except Exception as exc:
        print(f"Failed to query InfluxDB: {exc}")
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())