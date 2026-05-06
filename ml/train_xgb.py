"""
train_xgb.py
=============
Train separate XGBoost regressors for each forecast horizon in transformed.csv.

Usage:
    python train_xgb.py --input transformed.csv --output-dir model_output

Outputs:
    model_output/metrics.csv
    model_output/test_predictions.csv
    model_output/models/xgb_t_plus_<h>.json
    model_output/feature_columns.txt
    model_output/config.json
"""

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

try:
    import xgboost as xgb
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: xgboost. Install with: pip install xgboost"
    ) from exc


TARGET_PATTERN = re.compile(r"^target_water_level_t_plus_(\d+)$")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Train XGBoost models for each forecast horizon."
    )
    parser.add_argument("--input", default="transformed.csv", help="Input CSV path")
    parser.add_argument("--output-dir", default="model_output", help="Output directory")
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--n-estimators", type=int, default=1000)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--max-depth", type=int, default=6)
    parser.add_argument("--subsample", type=float, default=0.8)
    parser.add_argument("--colsample-bytree", type=float, default=0.8)
    parser.add_argument("--min-child-weight", type=float, default=1.0)
    parser.add_argument("--gamma", type=float, default=0.0)
    parser.add_argument("--n-jobs", type=int, default=-1)
    parser.add_argument("--early-stopping-rounds", type=int, default=50)
    return parser.parse_args()


def load_data(path):
    df = pd.read_csv(path)
    if "TimeStamp" not in df.columns:
        raise ValueError("Input data must include a TimeStamp column")
    df["TimeStamp"] = pd.to_datetime(df["TimeStamp"], errors="coerce")
    if df["TimeStamp"].isna().any():
        raise ValueError("TimeStamp contains invalid or missing values")
    df = df.sort_values("TimeStamp").reset_index(drop=True)
    return df


def get_targets_and_horizons(columns):
    targets = []
    for col in columns:
        match = TARGET_PATTERN.match(col)
        if match:
            targets.append((col, int(match.group(1))))
    if not targets:
        raise ValueError("No target columns found matching target_water_level_t_plus_*")
    targets.sort(key=lambda item: item[1])
    target_cols = [item[0] for item in targets]
    horizons = [item[1] for item in targets]
    return target_cols, horizons


def split_by_time(df, train_ratio, val_ratio):
    if not (0.0 < train_ratio < 1.0) or not (0.0 < val_ratio < 1.0):
        raise ValueError("train_ratio and val_ratio must be between 0 and 1")
    if train_ratio + val_ratio >= 1.0:
        raise ValueError("train_ratio + val_ratio must be less than 1")

    n_total = len(df)
    if n_total < 10:
        raise ValueError("Not enough rows for a 70/20/10 split")

    n_train = int(n_total * train_ratio)
    n_val = int(n_total * val_ratio)
    n_test = n_total - n_train - n_val
    if min(n_train, n_val, n_test) <= 0:
        raise ValueError("Split sizes too small; adjust ratios or add data")

    train_df = df.iloc[:n_train].copy()
    val_df = df.iloc[n_train : n_train + n_val].copy()
    test_df = df.iloc[n_train + n_val :].copy()
    return train_df, val_df, test_df


def evaluate_metrics(y_true, y_pred):
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2 = r2_score(y_true, y_pred)
    return {"mae": float(mae), "rmse": float(rmse), "r2": float(r2)}


def main():
    args = parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    model_dir = output_dir / "models"

    output_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    df = load_data(input_path)
    target_cols, horizons = get_targets_and_horizons(df.columns)
    feature_cols = [
        col for col in df.columns if col not in target_cols and col != "TimeStamp"
    ]
    if not feature_cols:
        raise ValueError("No feature columns found after excluding targets and TimeStamp")

    train_df, val_df, test_df = split_by_time(df, args.train_ratio, args.val_ratio)

    X_train = train_df[feature_cols]
    X_val = val_df[feature_cols]
    X_test = test_df[feature_cols]

    metrics_rows = []
    predictions = pd.DataFrame({"TimeStamp": test_df["TimeStamp"].values})

    xgb_params = {
        "n_estimators": args.n_estimators,
        "learning_rate": args.learning_rate,
        "max_depth": args.max_depth,
        "subsample": args.subsample,
        "colsample_bytree": args.colsample_bytree,
        "min_child_weight": args.min_child_weight,
        "gamma": args.gamma,
        "objective": "reg:squarederror",
        "eval_metric": "rmse",
        "random_state": args.random_state,
        "n_jobs": args.n_jobs,
    }

    for target_col, horizon in zip(target_cols, horizons):
        y_train = train_df[target_col]
        y_val = val_df[target_col]
        y_test = test_df[target_col]

        model = xgb.XGBRegressor(**xgb_params)
        fit_kwargs = {
            "eval_set": [(X_val, y_val)],
            "verbose": False,
        }
        if args.early_stopping_rounds > 0:
            fit_kwargs["early_stopping_rounds"] = args.early_stopping_rounds

        try:
            model.fit(X_train, y_train, **fit_kwargs)
        except TypeError as exc:
            if "early_stopping_rounds" not in str(exc):
                raise
            fit_kwargs.pop("early_stopping_rounds", None)
            model.fit(X_train, y_train, **fit_kwargs)

        y_val_pred = model.predict(X_val)
        y_test_pred = model.predict(X_test)

        val_metrics = evaluate_metrics(y_val, y_val_pred)
        test_metrics = evaluate_metrics(y_test, y_test_pred)

        metrics_rows.append(
            {
                "horizon": horizon,
                "target_col": target_col,
                "val_mae": val_metrics["mae"],
                "val_rmse": val_metrics["rmse"],
                "val_r2": val_metrics["r2"],
                "test_mae": test_metrics["mae"],
                "test_rmse": test_metrics["rmse"],
                "test_r2": test_metrics["r2"],
                "best_iteration": getattr(model, "best_iteration", None),
            }
        )

        predictions[f"y_true_t_plus_{horizon}"] = y_test.values
        predictions[f"y_pred_t_plus_{horizon}"] = y_test_pred

        model_path = model_dir / f"xgb_t_plus_{horizon}.json"
        model.save_model(model_path)

    metrics_df = pd.DataFrame(metrics_rows).sort_values("horizon")
    metrics_df.to_csv(output_dir / "metrics.csv", index=False)
    predictions.to_csv(output_dir / "test_predictions.csv", index=False)

    (output_dir / "feature_columns.txt").write_text(
        "\n".join(feature_cols), encoding="utf-8"
    )

    config = {
        "input": str(input_path),
        "output_dir": str(output_dir),
        "train_ratio": args.train_ratio,
        "val_ratio": args.val_ratio,
        "test_ratio": 1.0 - args.train_ratio - args.val_ratio,
        "row_counts": {
            "total": int(len(df)),
            "train": int(len(train_df)),
            "val": int(len(val_df)),
            "test": int(len(test_df)),
        },
        "horizons": horizons,
        "xgb_params": xgb_params,
        "early_stopping_rounds": args.early_stopping_rounds,
    }
    (output_dir / "config.json").write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )

    print("Training complete")
    print(f"Models saved to: {model_dir}")
    print(f"Metrics saved to: {output_dir / 'metrics.csv'}")
    print(f"Predictions saved to: {output_dir / 'test_predictions.csv'}")


if __name__ == "__main__":
    main()
