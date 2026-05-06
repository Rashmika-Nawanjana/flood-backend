#!/usr/bin/env python3
"""
Extract InfluxDB telemetry into adapter-ready JSON, convert to CSV,
transform to features, and run ML predictions.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import re

import pandas as pd
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from ml.transform import LAG_CONFIG


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="InfluxDB -> adapter JSON -> CSV -> features -> predict pipeline."
    )
    parser.add_argument("--target", type=int, default=None, help="Target station number")
    parser.add_argument(
        "--all-zones",
        action="store_true",
        help="Predict for every zone using upstream zones from Postgres",
    )
    parser.add_argument("--range", dest="time_range", default="1h", help="Flux range window")
    parser.add_argument("--limit", type=int, default=50, help="Max records to print")
    parser.add_argument("--fields", default=DEFAULT_FIELDS, help="Comma-separated field list")
    parser.add_argument(
        "--adapter-format",
        choices=["json", "ndjson"],
        default="json",
        help="Adapter output format",
    )
    parser.add_argument(
        "--mapping",
        default="ml/adapters/mapping_device_long.json",
        help="Mapping JSON for station adapter",
    )
    parser.add_argument(
        "--columns",
        default="ml/data.csv",
        help="CSV with header layout to match (optional)",
    )
    parser.add_argument("--work-dir", default="ml/pred_output", help="Working directory")
    parser.add_argument(
        "--output",
        default="ml/pred_output/predictions.csv",
        help="Predictions CSV path",
    )
    parser.add_argument("--model-dir", default="ml/model_output", help="Model directory")
    parser.add_argument("--no-sort", action="store_true", help="Do not sort rows by TimeStamp")
    parser.add_argument("--horizons", default=None, help="Comma-separated horizons to predict")

    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="Postgres connection string (env: DATABASE_URL)",
    )
    parser.add_argument(
        "--upstream-limit",
        type=int,
        default=2,
        help="Number of upstream zones to include (default: 2)",
    )
    parser.add_argument(
        "--sampling-minutes",
        type=int,
        default=60,
        help="Expected sampling interval in minutes (default: 60)",
    )
    parser.add_argument(
        "--model-id",
        type=int,
        default=None,
        help="Model metadata ID to store with predictions",
    )
    parser.add_argument(
        "--skip-db",
        action="store_true",
        help="Skip writing predictions to Postgres",
    )

    parser.add_argument("--url", default=None, help="InfluxDB URL")
    parser.add_argument("--token", default=None, help="InfluxDB token")
    parser.add_argument("--org", default=None, help="InfluxDB org")
    parser.add_argument("--bucket", default=None, help="InfluxDB bucket")
    parser.add_argument("--measurement", default=None, help="InfluxDB measurement")

    return parser.parse_args()


def run_step(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


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
                SELECT zone_id, river_id, prev_zone_id
                FROM zones
                """
            )
            zones = cur.fetchall()

    sensor_to_zone = {row["sensor_id"]: row["zone_id"] for row in sensors}
    zone_info = {
        row["zone_id"]: {
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


def safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value)


def resolve_model_id(database_url: str, explicit: int | None) -> int:
    if explicit is not None:
        return explicit
    if not database_url:
        raise ValueError("database_url is required to resolve model_id")

    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT model_id
                FROM model_metadata
                WHERE deployed_at IS NOT NULL
                ORDER BY deployed_at DESC, trained_at DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if row:
                return int(row["model_id"])

            cur.execute(
                """
                SELECT model_id
                FROM model_metadata
                ORDER BY trained_at DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if row:
                return int(row["model_id"])

    raise ValueError("No model_metadata entries available to resolve model_id")


def build_water_level_payload(df: pd.DataFrame) -> dict:
    horizon_cols = [col for col in df.columns if col.startswith("y_pred_t_plus_")]
    horizons = [int(col.split("_t_plus_")[-1]) for col in horizon_cols]

    records = []
    for _, row in df.iterrows():
        entry = {"timestamp": row["TimeStamp"]}
        for col in horizon_cols:
            value = row[col]
            entry[col] = None if pd.isna(value) else float(value)
        records.append(entry)

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "horizons": sorted(horizons),
        "records": records,
    }


def write_predictions_to_db(database_url: str, model_id: int, payloads: list[dict]) -> None:
    if not payloads:
        return

    insert = """
        INSERT INTO flood_predictions (zone_id, model_id, water_level)
        VALUES (%s, %s, %s)
    """
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for item in payloads:
                cur.execute(
                    insert,
                    (item["zone_id"], model_id, Json(item["water_level"])),
                )
        conn.commit()


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


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent.parent
    ml_dir = root / "ml"
    python = sys.executable

    if not args.all_zones and args.target is None:
        raise ValueError("--target is required unless --all-zones is set")

    max_lag = max(lag for lags in LAG_CONFIG.values() for lag in lags)
    min_seconds = (max_lag + 1) * args.sampling_minutes * 60
    requested_seconds = parse_time_range(args.time_range)
    if requested_seconds is not None and requested_seconds < min_seconds:
        adjusted = format_time_range(min_seconds)
        print(
            f"Adjusting range from {args.time_range} to {adjusted} to cover lag warmup"
        )
        args.time_range = adjusted

    work_dir = resolve_path(root, args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    adapter_output = work_dir / f"influx_adapter.{args.adapter_format}"
    raw_csv = work_dir / "input.csv"
    features_csv = work_dir / "features.csv"

    mapping_path = resolve_path(root, args.mapping)
    columns_path = resolve_path(root, args.columns)
    model_dir = resolve_path(root, args.model_dir)
    output_path = resolve_path(root, args.output)

    extract_cmd = [
        python,
        str(root / "scripts" / "extract_influx_data.py"),
        "--range",
        args.time_range,
        "--limit",
        str(args.limit),
        "--adapter-output",
        str(adapter_output),
        "--adapter-format",
        args.adapter_format,
    ]
    if args.fields:
        extract_cmd += ["--fields", args.fields]
    if args.url:
        extract_cmd += ["--url", args.url]
    if args.token:
        extract_cmd += ["--token", args.token]
    if args.org:
        extract_cmd += ["--org", args.org]
    if args.bucket:
        extract_cmd += ["--bucket", args.bucket]
    if args.measurement:
        extract_cmd += ["--measurement", args.measurement]

    print("\n[1/4] Extracting from InfluxDB...")
    run_step(extract_cmd, root)

    if args.all_zones:
        records = load_records(adapter_output)
        if not records:
            raise ValueError("No records returned from InfluxDB extraction")

        sensor_to_zone, zone_info = load_pg_mappings(args.database_url)
        zone_metrics = aggregate_zone_metrics(records, sensor_to_zone)
        if not zone_metrics:
            raise ValueError("No zone metrics available after aggregation")

        station_columns = []
        for station_idx in (1, 2, 3):
            for sensor in SENSORS:
                station_columns.append(f"station{station_idx}_{sensor}")
        csv_columns = ["TimeStamp"] + station_columns

        all_predictions = []
        db_payloads = []
        zones_dir = work_dir / "zones"
        zones_dir.mkdir(parents=True, exist_ok=True)

        for zone_id, info in zone_info.items():
            rows = build_zone_rows(zone_id, zone_metrics, zone_info, args.upstream_limit)
            if not rows:
                continue

            zone_dir = zones_dir / safe_name(zone_id)
            zone_dir.mkdir(parents=True, exist_ok=True)

            zone_raw_csv = zone_dir / "input.csv"
            zone_features_csv = zone_dir / "features.csv"
            zone_predictions_csv = zone_dir / "predictions.csv"

            df_raw = pd.DataFrame(rows, columns=csv_columns)
            df_raw.to_csv(zone_raw_csv, index=False)

            transform_cmd = [
                python,
                str(ml_dir / "transform_infer.py"),
                "--input",
                str(zone_raw_csv),
                "--target",
                "3",
                "--output",
                str(zone_features_csv),
            ]
            run_step(transform_cmd, root)

            df_features = pd.read_csv(zone_features_csv)
            if df_features.empty:
                continue

            predict_cmd = [
                python,
                str(ml_dir / "predict_xgb.py"),
                "--input",
                str(zone_features_csv),
                "--model-dir",
                str(model_dir),
                "--output",
                str(zone_predictions_csv),
            ]
            if args.horizons:
                predict_cmd += ["--horizons", args.horizons]
            run_step(predict_cmd, root)

            df_pred = pd.read_csv(zone_predictions_csv)
            if df_pred.empty:
                continue
            df_pred.insert(0, "zone_id", zone_id)
            df_pred.insert(0, "river_id", info.get("river_id"))
            all_predictions.append(df_pred)
            if not args.skip_db:
                db_payloads.append(
                    {
                        "zone_id": zone_id,
                        "water_level": build_water_level_payload(df_pred),
                    }
                )

        if not all_predictions:
            raise ValueError("No predictions generated for any zone")

        combined = pd.concat(all_predictions, ignore_index=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        combined.to_csv(output_path, index=False)

        if not args.skip_db:
            model_id = resolve_model_id(args.database_url, args.model_id)
            write_predictions_to_db(args.database_url, model_id, db_payloads)
            print("Stored predictions in flood_predictions table")

        print(f"\nDone. Predictions written to: {output_path}")
        return 0

    adapter_cmd = [
        python,
        str(ml_dir / "adapters" / "json_to_csv_station.py"),
        "--input",
        str(adapter_output),
        "--mapping",
        str(mapping_path),
        "--output",
        str(raw_csv),
    ]
    if columns_path.exists():
        adapter_cmd += ["--columns", str(columns_path)]
    if args.no_sort:
        adapter_cmd += ["--no-sort"]

    transform_cmd = [
        python,
        str(ml_dir / "transform_infer.py"),
        "--input",
        str(raw_csv),
        "--target",
        str(args.target),
        "--output",
        str(features_csv),
    ]

    predict_cmd = [
        python,
        str(ml_dir / "predict_xgb.py"),
        "--input",
        str(features_csv),
        "--model-dir",
        str(model_dir),
        "--output",
        str(output_path),
    ]
    if args.horizons:
        predict_cmd += ["--horizons", args.horizons]

    print("[2/4] Converting to CSV...")
    run_step(adapter_cmd, root)
    print("[3/4] Transforming features...")
    run_step(transform_cmd, root)
    print("[4/4] Running predictions...")
    run_step(predict_cmd, root)

    print(f"\nDone. Predictions written to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
