"""
run_predict_station.py
======================
Convert station-long JSON/NDJSON to CSV, transform to features, then predict.

Usage:
    python run_predict_station.py --input new.json --target 3 --mapping adapters/mapping_station_long.json
    python run_predict_station.py --input new.json --target 3 --mapping adapters/mapping_station_long.json --horizons 75
"""

import argparse
import subprocess
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run station-long JSON -> CSV -> transform -> predict in one command."
    )
    parser.add_argument("--input", required=True, help="Input JSON/NDJSON or CSV file")
    parser.add_argument("--target", type=int, required=True, help="Target station number")
    parser.add_argument("--output", default="pred_output/predictions.csv", help="Predictions CSV path")
    parser.add_argument("--work-dir", default="pred_output", help="Working directory for intermediate files")
    parser.add_argument("--model-dir", default="model_output", help="Directory containing trained models")
    parser.add_argument("--mapping", required=False, help="Mapping JSON file for station adapter")
    parser.add_argument("--records-key", default=None, help="JSON records key for adapter")
    parser.add_argument("--no-sort", action="store_true", help="Do not sort rows by TimeStamp")
    parser.add_argument("--columns", default=None, help="CSV file to read header from")
    parser.add_argument("--horizons", default=None, help="Comma-separated horizons to predict")
    return parser.parse_known_args()


def run_step(cmd, cwd):
    subprocess.run(cmd, cwd=cwd, check=True)


def main():
    args, extra = parse_args()
    cwd = Path(__file__).resolve().parent
    python = sys.executable

    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    input_path = Path(args.input)
    raw_csv = work_dir / "input.csv"
    features_csv = work_dir / "features.csv"

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
