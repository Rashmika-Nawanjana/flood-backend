"""
transform_infer.py
==================
Usage:
    python transform_infer.py --input data.csv --target 3 --output features.csv

Transforms raw sensor CSV into model-ready feature matrix for inference.
This emits features only (no future target columns).

Arguments:
    --input  Path to raw CSV (default: data.csv)
    --target Station number to predict for (e.g. 3)
    --output Path to save feature CSV (default: features.csv)
"""

import argparse
from pathlib import Path

import pandas as pd

from transform import LAG_CONFIG, FORECAST_HORIZONS, parse_stations


def transform_features(df, target_station, lag_config=LAG_CONFIG):
    df = df.copy()
    df["TimeStamp"] = pd.to_datetime(df["TimeStamp"], errors="coerce")
    if df["TimeStamp"].isna().any():
        raise ValueError("TimeStamp contains invalid or missing values")
    df = df.sort_values("TimeStamp").reset_index(drop=True)

    all_stations = parse_stations(df)
    if not all_stations:
        raise ValueError("No station columns found in input")

    # Only keep stations at or upstream of target (lower number = more upstream)
    relevant = sorted(k for k in all_stations if k <= target_station)
    if not relevant:
        raise ValueError(f"No stations found at or upstream of station{target_station}")

    print(f"\nTarget station   : station{target_station}")
    print(f"Upstream stations included: {[f'station{i}' for i in relevant]}")
    excluded = [k for k in all_stations if k > target_station]
    if excluded:
        print(f"Downstream stations excluded: {[f'station{k}' for k in excluded]}")

    sensors = list(next(iter(all_stations.values())).keys())
    print(f"Sensors          : {sensors}")
    print(f"Lag config       : {lag_config}")
    print(f"Forecast horizons: {FORECAST_HORIZONS}")

    # Build feature columns
    feature_cols = {}

    for station_idx in relevant:
        distance = target_station - station_idx
        lags = lag_config.get(distance)

        if lags is None:
            print(
                f"  Warning: No lag config for distance {distance} (station{station_idx})"
            )
            continue

        for sensor in sensors:
            raw_col = all_stations[station_idx].get(sensor)
            if raw_col is None:
                continue
            series = pd.to_numeric(df[raw_col], errors="coerce")
            for lag in lags:
                col_name = f"station{station_idx}_{sensor}_lag{lag}"
                feature_cols[col_name] = series.shift(lag)

    out = pd.DataFrame({"TimeStamp": df["TimeStamp"]})
    for name, col in feature_cols.items():
        out[name] = col.values

    before = len(out)
    max_lag = max(l for lags in lag_config.values() for l in lags)
    out = out.iloc[max_lag:].reset_index(drop=True)
    after = len(out)

    print(f"\nRows in raw data : {before}")
    print(f"Rows dropped     : {before - after}  (first {max_lag} rows = lag warmup)")
    print(f"Rows in output   : {after}")
    print(f"Feature columns  : {len(feature_cols)}")
    print("Target columns   : 0 (inference mode)")
    print(f"Total columns    : {out.shape[1]}  (TimeStamp + features)")

    return out


def main():
    parser = argparse.ArgumentParser(
        description="Transform raw flood sensor CSV into inference feature matrix."
    )
    parser.add_argument("--input", default="data.csv", help="Input CSV path")
    parser.add_argument("--target", type=int, required=True, help="Target station number")
    parser.add_argument("--output", default="features.csv", help="Output CSV path")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input not found: {input_path}")

    print(f"Reading  : {args.input}")
    df = pd.read_csv(args.input)
    print(f"Shape    : {df.shape[0]} rows x {df.shape[1]} columns")

    out = transform_features(df, target_station=args.target)

    out.to_csv(args.output, index=False)
    print(f"\nSaved -> {args.output}")


if __name__ == "__main__":
    main()
