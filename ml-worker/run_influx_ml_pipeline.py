#!/usr/bin/env python3
"""Extract InfluxDB telemetry, transform features, run inference, and persist results."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

from ml.transform import LAG_CONFIG

from pipeline.influx import (
    DEFAULT_FIELDS,
    METRIC_MAP,
    SENSORS,
    aggregate_zone_metrics,
    build_zone_rows,
    format_time_range,
    get_upstream_chain,
    load_pg_mappings,
    load_records,
    parse_time_range,
    to_float,
)
from pipeline.predictions import (
    build_water_level_payload,
    color_for_severity,
    create_kafka_producer,
    publish_zone_events,
    resolve_model_id,
    safe_name,
    severity_from_peak,
    summarize_zone_prediction,
    write_predictions_to_db,
)


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
    parser.add_argument(
        "--skip-kafka",
        action="store_true",
        help="Skip publishing prediction/risk/alert events to Kafka",
    )
    parser.add_argument(
        "--kafka-broker",
        default=os.getenv("KAFKA_BROKER"),
        help="Kafka bootstrap server (env: KAFKA_BROKER)",
    )
    parser.add_argument(
        "--analytics-topic",
        default=os.getenv("ANALYTICS_PREDICTIONS_TOPIC", "analytics.predictions"),
        help="Kafka topic for zone:risk:update and prediction:new",
    )
    parser.add_argument(
        "--alerts-topic",
        default=os.getenv("SYSTEM_ALERTS_TOPIC", "system.alerts"),
        help="Kafka topic for alert:new",
    )
    parser.add_argument(
        "--risk-warning-m",
        type=float,
        default=float(os.getenv("RISK_WARNING_M", "3.0")),
        help="Water level (m) threshold for HIGH",
    )
    parser.add_argument(
        "--risk-critical-m",
        type=float,
        default=float(os.getenv("RISK_CRITICAL_M", "4.0")),
        help="Water level (m) threshold for CRITICAL",
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
        kafka_producer = None
        if not args.skip_kafka:
            kafka_producer = create_kafka_producer(args.kafka_broker)

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
            zone_name = info.get("zone_name") or zone_id
            if kafka_producer is not None:
                summary = summarize_zone_prediction(
                    zone_id=zone_id,
                    zone_name=zone_name,
                    df_pred=df_pred,
                    warning_m=args.risk_warning_m,
                    critical_m=args.risk_critical_m,
                )
                publish_zone_events(
                    producer=kafka_producer,
                    analytics_topic=args.analytics_topic,
                    alerts_topic=args.alerts_topic,
                    summary=summary,
                )
            df_pred.insert(0, "zone_id", zone_id)
            df_pred.insert(1, "zone_name", zone_name)
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

        if kafka_producer is not None:
            kafka_producer.flush()
            kafka_producer.close()
            print(
                f"Published ML events to Kafka topics: {args.analytics_topic} (prediction:new, zone:risk:update), {args.alerts_topic} (alert:new)"
            )

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