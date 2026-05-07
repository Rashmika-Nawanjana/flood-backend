"""
run_all.py
==========
Run the full pipeline: transform raw data, then train per-horizon XGBoost models.

Usage:
    python run_all.py --input data.csv --target 3 --transformed transformed.csv --output-dir model_output

Any extra args after `--` are passed to train_xgb.py.
Example:
    python run_all.py --input data.csv --target 3 -- --learning-rate 0.1 --max-depth 4
"""

import argparse
import subprocess
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run transform.py then train_xgb.py in one command."
    )
    parser.add_argument("--input", default="data.csv", help="Raw input CSV path")
    parser.add_argument("--target", type=int, required=True, help="Target station number")
    parser.add_argument(
        "--transformed",
        default="transformed.csv",
        help="Output path for transformed features",
    )
    parser.add_argument(
        "--output-dir",
        default="model_output",
        help="Directory for training outputs",
    )
    return parser.parse_known_args()


def run_step(cmd, cwd):
    subprocess.run(cmd, cwd=cwd, check=True)


def main():
    args, extra = parse_args()
    cwd = Path(__file__).resolve().parent
    python = sys.executable

    transform_cmd = [
        python,
        "transform.py",
        "--input",
        args.input,
        "--target",
        str(args.target),
        "--output",
        args.transformed,
    ]

    train_cmd = [
        python,
        "train_xgb.py",
        "--input",
        args.transformed,
        "--output-dir",
        args.output_dir,
    ] + extra

    print("Running transform step...")
    run_step(transform_cmd, cwd)

    print("Running training step...")
    run_step(train_cmd, cwd)

    print("Pipeline complete")


if __name__ == "__main__":
    main()
