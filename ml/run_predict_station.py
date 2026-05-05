"""
run_predict_station.py
======================
Convert station-long JSON/NDJSON to CSV, transform to features, then predict.

Usage:
    python run_predict_station.py --input new.json --target 3 --mapping adapters/mapping_station_long.json
    python run_predict_station.py --input new.json --target 3 --mapping adapters/mapping_station_long.json --horizons 75
    python run_predict_station.py --influx --target 3 --mapping adapters/mapping_station_long.json
"""

import argparse
import subprocess
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run station-long JSON -> CSV -> transform -> predict in one command."
    )
    parser.add_argument("--input", help="Input JSON/NDJSON or CSV file")
    parser.add_argument(
        "--influx",
        action="store_true",
        help="Fetch input from InfluxDB instead of a file",
    )
    parser.add_argument("--target", type=int, required=True, help="Target station number")
    parser.add_argument("--output", default="pred_output/predictions.csv", help="Predictions CSV path")
    parser.add_argument("--work-dir", default="pred_output", help="Working directory for intermediate files")
    parser.add_argument("--model-dir", default="model_output", help="Directory containing trained models")
    parser.add_argument("--mapping", required=False, help="Mapping JSON file for station adapter")
    parser.add_argument("--records-key", default=None, help="JSON records key for adapter")
    parser.add_argument("--no-sort", action="store_true", help="Do not sort rows by TimeStamp")
    parser.add_argument("--columns", default=None, help="CSV file to read header from")
    parser.add_argument("--horizons", default=None, help="Comma-separated horizons to predict")
    parser.add_argument("--influx-url", default=None, help="InfluxDB URL")
    parser.add_argument("--influx-org", default=None, help="InfluxDB org")
    parser.add_argument("--influx-token", default=None, help="InfluxDB token")
    parser.add_argument("--influx-bucket", default=None, help="InfluxDB bucket")
    parser.add_argument("--influx-measurement", default=None, help="InfluxDB measurement")
    parser.add_argument("--influx-start", default=None, help="Flux range start (e.g. -24h)")
    parser.add_argument("--influx-stop", default=None, help="Flux range stop")
    parser.add_argument("--influx-station-tag", default=None, help="Station tag key")
    parser.add_argument("--influx-fields", default=None, help="Comma-separated field list")
    parser.add_argument("--influx-time-column", default=None, help="Time column in query results")
    parser.add_argument("--influx-query", default=None, help="Raw Flux query to run")
    return parser.parse_known_args()


def run_step(cmd, cwd):
    subprocess.run(cmd, cwd=cwd, check=True)


def main():
    args, extra = parse_args()
    cwd = Path(__file__).resolve().parent
    python = sys.executable

    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    if not args.influx and not args.input:
        raise ValueError("--input is required unless --influx is set")

    raw_csv = work_dir / "input.csv"
    features_csv = work_dir / "features.csv"

    if args.influx:
        if not args.mapping:
            raise ValueError("--mapping is required for InfluxDB input")

        adapter_cmd = [
            python,
            "adapters/influx_to_csv_station.py",
            "--mapping",
            args.mapping,
            "--output",
            str(raw_csv),
        ]

        if args.columns:
            adapter_cmd += ["--columns", args.columns]
        if args.no_sort:
            adapter_cmd += ["--no-sort"]

        if args.influx_url:
            adapter_cmd += ["--url", args.influx_url]
        if args.influx_org:
            adapter_cmd += ["--org", args.influx_org]
        if args.influx_token:
            adapter_cmd += ["--token", args.influx_token]
        if args.influx_bucket:
            adapter_cmd += ["--bucket", args.influx_bucket]
        if args.influx_measurement:
            adapter_cmd += ["--measurement", args.influx_measurement]
        if args.influx_start:
            adapter_cmd += ["--start", args.influx_start]
        if args.influx_stop:
            adapter_cmd += ["--stop", args.influx_stop]
        if args.influx_station_tag:
            adapter_cmd += ["--station-tag", args.influx_station_tag]
        if args.influx_fields:
            adapter_cmd += ["--fields", args.influx_fields]
        if args.influx_time_column:
            adapter_cmd += ["--time-column", args.influx_time_column]
        if args.influx_query:
            adapter_cmd += ["--query", args.influx_query]

        print("Running InfluxDB adapter step...")
        run_step(adapter_cmd, cwd)
    else:
        input_path = Path(args.input)
        if input_path.suffix.lower() == ".csv":
            raw_csv = input_path
        else:
            if not args.mapping:
                raise ValueError("--mapping is required for JSON/NDJSON input")

            adapter_cmd = [
                python,
                "adapters/json_to_csv_station.py",
                "--input",
                str(input_path),
                "--output",
                str(raw_csv),
                "--mapping",
                args.mapping,
            ]

            columns_path = args.columns
            if not columns_path:
                default_columns = cwd / "data.csv"
                if default_columns.exists():
                    columns_path = str(default_columns)
            if columns_path:
                adapter_cmd += ["--columns", columns_path]

            if args.records_key:
                adapter_cmd += ["--records-key", args.records_key]
            if args.no_sort:
                adapter_cmd += ["--no-sort"]

            print("Running adapter step...")
            run_step(adapter_cmd, cwd)

    transform_cmd = [
        python,
        "transform_infer.py",
        "--input",
        str(raw_csv),
        "--target",
        str(args.target),
        "--output",
        str(features_csv),
    ]
    print("Running transform step...")
    run_step(transform_cmd, cwd)

    predict_cmd = [
        python,
        "predict_xgb.py",
        "--input",
        str(features_csv),
        "--model-dir",
        args.model_dir,
        "--output",
        args.output,
    ]
    if args.horizons:
        predict_cmd += ["--horizons", args.horizons]

    predict_cmd += extra

    print("Running predict step...")
    run_step(predict_cmd, cwd)

    print(f"Done. Predictions in {args.output}")


if __name__ == "__main__":
    main()
