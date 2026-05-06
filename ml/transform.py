"""
transform.py
============
Usage:
    python transform.py --input data.csv --target 3 --output transformed.csv

Takes raw sensor data.csv and outputs a transformed feature CSV
ready for model training.

Arguments:
    --input     Path to raw CSV (default: data.csv)
    --target    Station number to predict for (e.g. 3)
    --output    Path to save transformed CSV (default: transformed.csv)
"""

import argparse
import re
import sys
import pandas as pd
import numpy as np

# ── Lag configuration (edit here) ────────────────────────────────────────────
# Key   = upstream distance from target station
#           0 = target station itself
#           1 = one station upstream
#           2 = two stations upstream
# Value = list of lag steps (in timesteps) to use from that station

LAG_CONFIG = {
    0: [0, 1],      # target station   → readings at t,   t-1
    1: [2, 3],      # 1 step upstream  → readings at t-2, t-3
    2: [3, 5],      # 2 steps upstream → readings at t-3, t-5
}

# Future horizons to predict (in timesteps ahead)
FORECAST_HORIZONS = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75]

# ─────────────────────────────────────────────────────────────────────────────


def parse_stations(df):
    """
    Detect station numbers and their sensor columns from column names.
    Returns: { station_num: { sensor_name: column_name } }
    e.g.     { 1: {'water_level': 'station1_water_level', ...}, 2: {...} }
    """
    pattern = re.compile(r"^station(\d+)_(.+)$", re.IGNORECASE)
    stations = {}
    for col in df.columns:
        m = pattern.match(col)
        if m:
            idx = int(m.group(1))
            sensor = m.group(2).lower()
            stations.setdefault(idx, {})[sensor] = col
    return dict(sorted(stations.items()))


def transform(df, target_station, lag_config=LAG_CONFIG, horizons=FORECAST_HORIZONS):
    """
    Transform raw sensor DataFrame into feature + target matrix.

    For each row (timestep t):
      - Features: sensor readings from target station and upstream stations,
                  pulled at the configured lag offsets.
      - Targets:  water_level at the target station at each future horizon.

    Rows that don't have enough history (lag warmup) or enough future data
    (horizon cutoff) are dropped automatically.
    """
    df = df.copy()
    df["TimeStamp"] = pd.to_datetime(df["TimeStamp"])
    df = df.sort_values("TimeStamp").reset_index(drop=True)

    all_stations = parse_stations(df)

    # Only keep stations at or upstream of target (lower number = more upstream)
    relevant = sorted(k for k in all_stations if k <= target_station)

    print(f"\nTarget station   : station{target_station}")
    print(f"Upstream stations included: {[f'station{i}' for i in relevant]}")
    excluded = [k for k in all_stations if k > target_station]
    if excluded:
        print(f"Downstream stations excluded: {[f'station{k}' for k in excluded]}")

    sensors = list(next(iter(all_stations.values())).keys())
    print(f"Sensors          : {sensors}")
    print(f"Lag config       : {lag_config}")
    print(f"Forecast horizons: {horizons}")

    # ── Build feature columns ─────────────────────────────────────────────────
    feature_cols = {}

    for station_idx in relevant:
        distance = target_station - station_idx   # 0=self, 1=1-upstream, 2=2-upstream
        lags = lag_config.get(distance)

        if lags is None:
            print(f"  ⚠  No lag config for distance {distance} (station{station_idx}) — skipped")
            continue

        for sensor in sensors:
            raw_col = all_stations[station_idx].get(sensor)
            if raw_col is None:
                continue
            series = pd.to_numeric(df[raw_col], errors="coerce")
            for lag in lags:
                col_name = f"station{station_idx}_{sensor}_lag{lag}"
                feature_cols[col_name] = series.shift(lag)

    # ── Build target columns ──────────────────────────────────────────────────
    wl_col = all_stations[target_station].get("water_level")
    if wl_col is None:
        raise ValueError(f"station{target_station} has no water_level column")

    target_series = pd.to_numeric(df[wl_col], errors="coerce")
    target_cols = {}
    for h in horizons:
        target_cols[f"target_water_level_t_plus_{h}"] = target_series.shift(-h)

    # ── Assemble output DataFrame ─────────────────────────────────────────────
    out = pd.DataFrame({"TimeStamp": df["TimeStamp"]})
    for name, col in feature_cols.items():
        out[name] = col.values
    for name, col in target_cols.items():
        out[name] = col.values

    before = len(out)
    out = out.dropna().reset_index(drop=True)
    after = len(out)

    max_lag = max(l for lags in lag_config.values() for l in lags)
    max_horizon = max(horizons)
    print(f"\nRows in raw data : {before}")
    print(f"Rows dropped     : {before - after}  "
          f"(first {max_lag} rows = lag warmup, "
          f"last {max_horizon} rows = no future data yet)")
    print(f"Rows in output   : {after}")
    print(f"Feature columns  : {len(feature_cols)}")
    print(f"Target columns   : {len(target_cols)}")
    print(f"Total columns    : {out.shape[1]}  (TimeStamp + features + targets)")

    return out


def main():
    parser = argparse.ArgumentParser(
        description="Transform raw flood sensor CSV into model-ready feature matrix."
    )
    parser.add_argument("--input",  default="data.csv",        help="Input CSV path")
    parser.add_argument("--target", type=int, required=True,   help="Target station number")
    parser.add_argument("--output", default="transformed.csv", help="Output CSV path")
    args = parser.parse_args()

    print(f"Reading  : {args.input}")
    df = pd.read_csv(args.input)
    print(f"Shape    : {df.shape[0]} rows × {df.shape[1]} columns")

    out = transform(df, target_station=args.target)

    out.to_csv(args.output, index=False)
    print(f"\nSaved → {args.output}")

    # Print a preview
    print("\n── First 3 rows of output ──")
    print(out.head(3).to_string())
    print("\n── Column list ──")
    for col in out.columns:
        print(f"  {col}")


if __name__ == "__main__":
    main()
