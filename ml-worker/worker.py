#!/usr/bin/env python3
"""Run the ML inference pipeline on a fixed interval inside Docker.

The worker repeatedly invokes the moved ml-worker/run_influx_ml_pipeline.py
script so the prediction flow starts automatically with the stack and persists
results to Postgres.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PIPELINE = ROOT / "ml-worker" / "run_influx_ml_pipeline.py"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def getenv_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def getenv_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def build_pipeline_command() -> list[str]:
    command = [sys.executable, str(PIPELINE)]

    if getenv_bool("ML_PIPELINE_ALL_ZONES", True):
        command.append("--all-zones")
    else:
        target = os.getenv("ML_PIPELINE_TARGET")
        if not target:
            raise ValueError(
                "ML_PIPELINE_TARGET is required when ML_PIPELINE_ALL_ZONES is false"
            )
        command.extend(["--target", target])

    command.extend(["--range", os.getenv("ML_PIPELINE_TIME_RANGE", "1h")])
    command.extend(["--limit", os.getenv("ML_PIPELINE_LIMIT", "50")])
    command.extend(["--upstream-limit", os.getenv("ML_PIPELINE_UPSTREAM_LIMIT", "2")])
    command.extend(["--sampling-minutes", os.getenv("ML_PIPELINE_SAMPLING_MINUTES", "60")])

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is required for the ML worker")
    command.extend(["--database-url", database_url])

    model_id = os.getenv("ML_PIPELINE_MODEL_ID")
    if model_id:
        command.extend(["--model-id", model_id])

    horizons = os.getenv("ML_PIPELINE_HORIZONS")
    if horizons:
        command.extend(["--horizons", horizons])

    if getenv_bool("ML_PIPELINE_SKIP_DB", False):
        command.append("--skip-db")

    kafka_broker = os.getenv("KAFKA_BROKER")
    if getenv_bool("ML_PIPELINE_SKIP_KAFKA", False):
        command.append("--skip-kafka")
    elif kafka_broker:
        command.extend(["--kafka-broker", kafka_broker])

    analytics_topic = os.getenv("ANALYTICS_PREDICTIONS_TOPIC")
    if analytics_topic:
        command.extend(["--analytics-topic", analytics_topic])

    alerts_topic = os.getenv("SYSTEM_ALERTS_TOPIC")
    if alerts_topic:
        command.extend(["--alerts-topic", alerts_topic])

    warning_threshold = os.getenv("RISK_WARNING_M")
    if warning_threshold:
        command.extend(["--risk-warning-m", warning_threshold])

    critical_threshold = os.getenv("RISK_CRITICAL_M")
    if critical_threshold:
        command.extend(["--risk-critical-m", critical_threshold])

    return command


def run_pipeline() -> None:
    command = build_pipeline_command()
    print(f"[{now_utc_iso()}] Running ML pipeline")
    subprocess.run(command, cwd=ROOT, check=True)
    print(f"[{now_utc_iso()}] ML pipeline completed successfully")


def main() -> int:
    interval_seconds = getenv_int("ML_PIPELINE_INTERVAL_SECONDS", 900)
    run_once = getenv_bool("ML_PIPELINE_ONCE", False)

    while True:
        try:
            run_pipeline()
        except subprocess.CalledProcessError as exc:
            print(f"[{now_utc_iso()}] ML pipeline failed with exit code {exc.returncode}")
        except Exception as exc:
            print(f"[{now_utc_iso()}] ML worker error: {exc}")

        if run_once:
            return 0

        print(f"[{now_utc_iso()}] Sleeping for {interval_seconds} seconds")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())