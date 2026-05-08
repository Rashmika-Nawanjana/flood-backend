"""
predict_xgb.py
==============
Make predictions using trained XGBoost models for each forecast horizon.

Usage:
    python predict_xgb.py --input features.csv --model-dir model_output --output predictions.csv
    python predict_xgb.py --input features.csv --model-dir model_output --output predictions.csv --horizons 75

Outputs:
    predictions.csv (columns: TimeStamp, y_pred_t_plus_5, y_pred_t_plus_10, ...)
"""

import argparse
import json
import re
from pathlib import Path

import pandas as pd

try:
    import xgboost as xgb
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: xgboost. Install with: pip install xgboost"
    ) from exc


MODEL_PATTERN = re.compile(r"xgb_t_plus_(\d+)\.json$")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Make predictions using trained XGBoost models."
    )
    parser.add_argument("--input", default="features.csv", help="Input CSV path")
    parser.add_argument("--model-dir", default="model_output", help="Model directory")
    parser.add_argument("--output", default="predictions.csv", help="Output CSV path")
    parser.add_argument(
        "--horizons",
        default=None,
        help="Comma-separated list of horizons to predict (default: all from config)",
    )
    return parser.parse_args()


def parse_horizons(value):
    if not value:
        return None
    text = value.strip().lower()
    if text == "all":
        return None
    horizons = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            horizons.append(int(item))
        except ValueError as exc:
            raise ValueError(f"Invalid horizon: {item}") from exc
    return horizons


def load_data(path):
    df = pd.read_csv(path)
    if "TimeStamp" not in df.columns:
        raise ValueError("Input data must include a TimeStamp column")
    df["TimeStamp"] = pd.to_datetime(df["TimeStamp"], errors="coerce")
    if df["TimeStamp"].isna().any():
        raise ValueError("TimeStamp contains invalid or missing values")
    return df


def load_feature_columns(model_dir):
    feature_path = Path(model_dir) / "feature_columns.txt"
    if not feature_path.exists():
        raise FileNotFoundError(f"Feature columns file not found: {feature_path}")
    return [line.strip() for line in feature_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_config_horizons(model_dir):
    config_path = Path(model_dir) / "config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        return [int(h) for h in config.get("horizons", [])]
    return []


def scan_model_horizons(model_dir):
    models_path = Path(model_dir) / "models"
    if not models_path.exists():
        return []
    horizons = []
    for path in models_path.iterdir():
        match = MODEL_PATTERN.search(path.name)
        if match:
            horizons.append(int(match.group(1)))
    return sorted(horizons)


def resolve_horizons(model_dir, requested):
    available = load_config_horizons(model_dir)
    if not available:
        available = scan_model_horizons(model_dir)
    if not available:
        raise FileNotFoundError("No trained models found in model_dir")

    if not requested:
        return sorted(available)

    missing = [h for h in requested if h not in available]
    if missing:
        raise ValueError(f"Requested horizons not found in model_dir: {missing}")
    return requested



def publish_prediction_events(predictions_df, args):
    """
    Publish summarized prediction events to Kafka using real prediction values.

    - Determines `zone_id` and `zone_name` from DataFrame if present.
    - Summarizes the latest row across horizon columns to find predicted peak and horizon.
    - Publishes `zone:risk:update` and `prediction:new` to `analytics.predictions`.
    - Publishes `alert:new` to `system.alerts` when severity is HIGH/CRITICAL.

    This replaces the previous mock publisher and uses values from `predictions_df`.
    """
    try:
        from kafka import KafkaProducer
        from datetime import datetime, timezone
        import json
        import os

        kafka_broker = os.getenv("KAFKA_BROKER", "localhost:9092")

        producer = KafkaProducer(
            bootstrap_servers=kafka_broker,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks="all",
        )

        # determine zone info if available
        if "zone_id" in predictions_df.columns:
            zone_id = str(predictions_df.iloc[-1].get("zone_id"))
        else:
            zone_id = os.getenv("ZONE_ID", "UNKNOWN")
        if "zone_name" in predictions_df.columns:
            zone_name = str(predictions_df.iloc[-1].get("zone_name"))
        else:
            zone_name = os.getenv("ZONE_NAME", "UNKNOWN")

        # find horizon columns
        horizon_cols = [c for c in predictions_df.columns if c.startswith("y_pred_t_plus_")]
        if not horizon_cols:
            print("No horizon prediction columns found; skipping publish.")
            return

        latest = predictions_df.iloc[-1]
        valid = []
        for col in horizon_cols:
            val = latest.get(col)
            if pd.isna(val):
                continue
            minutes = int(col.split("_t_plus_")[-1])
            valid.append((minutes, float(val), col))

        if not valid:
            print("No valid prediction values in latest row; skipping publish.")
            return

        # peak horizon and value
        peak_minutes, peak_level_m, peak_col = max(valid, key=lambda t: t[1])

        # severity thresholds (defaults; override with env vars)
        warning_m = float(os.getenv("RISK_WARNING_M", "3.0"))
        critical_m = float(os.getenv("RISK_CRITICAL_M", "5.0"))
        def severity_from_peak(level):
            if level >= critical_m:
                return "CRITICAL"
            if level >= warning_m:
                return "HIGH"
            if level >= warning_m * 0.75:
                return "MEDIUM"
            return "LOW"

        severity = severity_from_peak(peak_level_m)

        # compute estimated flood time from TimeStamp column if present
        try:
            ts_raw = latest.get("TimeStamp")
            if isinstance(ts_raw, str):
                base_ts = pd.to_datetime(ts_raw)
            else:
                base_ts = pd.to_datetime(ts_raw)
            if base_ts.tzinfo is None:
                base_ts = base_ts.tz_localize("UTC")
            estimated_flood_time = (base_ts + pd.Timedelta(minutes=peak_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            estimated_flood_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        prediction_id = f"PRED-{zone_id}-{int(datetime.now(timezone.utc).timestamp())}"

        # publish zone:risk:update
        risk_event = {
            "event": "zone:risk:update",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "data": {
                "zone_id": zone_id,
                "zone_name": zone_name,
                "previous_level": "UNKNOWN",
                "current_level": severity,
                "risk_score": round(min(100.0, max(0.0, (peak_level_m / max(critical_m, 0.0001)) * 100.0)), 1),
                "color_code": "#F97316" if severity in {"HIGH", "CRITICAL"} else "#22C55E",
            },
        }
        producer.send(os.getenv("ANALYTICS_TOPIC", "analytics.predictions"), risk_event)

        # publish prediction:new
        pred_event = {
            "event": "prediction:new",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "data": {
                "prediction_id": prediction_id,
                "zone_id": zone_id,
                "zone_name": zone_name,
                "predicted_peak_level_m": round(float(peak_level_m), 4),
                "estimated_flood_time": estimated_flood_time,
                "severity": severity,
                "top_risk_factors": [
                    {"factor": peak_col, "value": round(float(peak_level_m), 4), "impact": "High"}
                ],
            },
        }
        producer.send(os.getenv("ANALYTICS_TOPIC", "analytics.predictions"), pred_event)

        # if high severity, also publish alert
        if severity in {"HIGH", "CRITICAL"}:
            alert_event = {
                "event": "alert:new",
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "data": {
                    "alert_id": f"ALT-{zone_id}-{int(datetime.now(timezone.utc).timestamp())}",
                    "zone_id": zone_id,
                    "severity": severity,
                    "title": f"Automated ML alert: {severity} flood risk for {zone_name}",
                    "message": "Model predicts elevated water levels. Follow local guidance.",
                    "recommended_action": "EVACUATE" if severity == "CRITICAL" else "PREPARE",
                    "recommended_shelters": [],
                },
            }
            producer.send(os.getenv("ALERTS_TOPIC", "system.alerts"), alert_event)

        producer.flush()
        print("Successfully published ML events to Kafka.")
    except Exception as e:
        print(f"Failed to publish to Kafka: {e}")


def main():
    args = parse_args()
    requested = parse_horizons(args.horizons)

    df = load_data(args.input)
    feature_cols = load_feature_columns(args.model_dir)

    missing = [col for col in feature_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Missing features in input: {missing}")

    horizons = resolve_horizons(args.model_dir, requested)

    X = df[feature_cols].apply(pd.to_numeric, errors="coerce")
    predictions = pd.DataFrame({"TimeStamp": df["TimeStamp"].values})

    models_dir = Path(args.model_dir) / "models"
    for horizon in horizons:
        model_path = models_dir / f"xgb_t_plus_{horizon}.json"
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")

        model = xgb.XGBRegressor()
        model.load_model(str(model_path))
        pred = model.predict(X)
        predictions[f"y_pred_t_plus_{horizon}"] = pred

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(output_path, index=False)

    # publish ML events derived from predictions (if invoked in standalone mode)
    try:
        publish_prediction_events(predictions, args)
    except Exception:
        # publishing is best-effort; avoid crashing the prediction run
        pass

    print(f"Predictions saved to: {output_path}")


if __name__ == "__main__":
    main()
