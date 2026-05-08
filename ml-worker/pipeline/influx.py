from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

import pandas as pd
import psycopg
from psycopg.rows import dict_row


DEFAULT_FIELDS = (
    "water_level_cm,pressure,flow_velocity_ms,rainfall_intensity_mmh,"
    "temperature,battery_voltage,signal_strength_dbm"
)

METRIC_MAP = {
    "water_level_cm": "water_level",
    "pressure": "pressure",
    "flow_velocity_ms": "velocity",
    "rainfall_intensity_mmh": "rainfall",
}

SENSORS = ["velocity", "water_level", "pressure", "rainfall"]


def parse_time_range(value: str) -> int | None:
    if not value:
        return None
    match = re.match(r"^(\d+)([smhdw])$", value.strip().lower())
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2)
    multipliers = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
        "w": 604800,
    }
    return amount * multipliers[unit]


def format_time_range(seconds: int) -> str:
    if seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    if seconds % 60 == 0:
        return f"{seconds // 60}m"
    return f"{seconds}s"


def load_records(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text[0] in "[{":
        payload = json.loads(text)
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return [payload]
    records = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def to_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_pg_mappings(database_url: str):
    if not database_url:
        raise ValueError("database_url is required for --all-zones")

    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sensor_id, zone_id
                FROM sensor_nodes
                WHERE zone_id IS NOT NULL
                  AND is_active IS TRUE
                """
            )
            sensors = cur.fetchall()

            cur.execute(
                """
                SELECT zone_id, zone_name, river_id, prev_zone_id
                FROM zones
                """
            )
            zones = cur.fetchall()

    sensor_to_zone = {row["sensor_id"]: row["zone_id"] for row in sensors}
    zone_info = {
        row["zone_id"]: {
            "zone_name": row.get("zone_name") or row["zone_id"],
            "river_id": row["river_id"],
            "prev_zone_id": row["prev_zone_id"],
        }
        for row in zones
    }
    return sensor_to_zone, zone_info


def aggregate_zone_metrics(records, sensor_to_zone):
    sums = defaultdict(float)
    counts = defaultdict(int)

    for record in records:
        if not isinstance(record, dict):
            continue
        device_id = record.get("device_id")
        if not device_id:
            continue
        zone_id = sensor_to_zone.get(device_id)
        if not zone_id:
            continue
        timestamp = record.get("timestamp")
        if not timestamp:
            continue

        for src, dest in METRIC_MAP.items():
            if src not in record:
                continue
            value = to_float(record.get(src))
            if value is None:
                continue
            key = (zone_id, timestamp, dest)
            sums[key] += value
            counts[key] += 1

    zone_ts = defaultdict(dict)
    for (zone_id, timestamp, sensor), total in sums.items():
        avg = total / counts[(zone_id, timestamp, sensor)]
        zone_ts.setdefault(zone_id, {}).setdefault(timestamp, {})[sensor] = avg

    return zone_ts


def get_upstream_chain(zone_id, zone_info, limit):
    chain = []
    current = zone_id
    base_river = zone_info.get(zone_id, {}).get("river_id")
    for _ in range(limit):
        prev_zone = zone_info.get(current, {}).get("prev_zone_id")
        if not prev_zone:
            break
        if zone_info.get(prev_zone, {}).get("river_id") != base_river:
            break
        chain.append(prev_zone)
        current = prev_zone
    return chain


def build_zone_rows(zone_id, zone_metrics, zone_info, upstream_limit):
    timestamps = sorted(zone_metrics.get(zone_id, {}).keys())
    if not timestamps:
        return []

    upstream = get_upstream_chain(zone_id, zone_info, upstream_limit)
    station_map = {
        1: upstream[1] if len(upstream) >= 2 else None,
        2: upstream[0] if len(upstream) >= 1 else None,
        3: zone_id,
    }

    rows = []
    for timestamp in timestamps:
        row = {"TimeStamp": timestamp}
        for station_idx in (1, 2, 3):
            zone = station_map.get(station_idx)
            data = zone_metrics.get(zone, {}).get(timestamp, {}) if zone else {}
            for sensor in SENSORS:
                row[f"station{station_idx}_{sensor}"] = data.get(sensor)
        rows.append(row)
    return rows