"""
json_to_csv_station.py
======================
Convert long-format station JSON/NDJSON into a wide CSV matching data.csv.

Each record should look like:
    {"station": 3, "timestamp": "2026-05-03 00:00:00", "water_level_cm": 123.4, ...}

Mapping file schema:
{
  "station_field": "station",
  "timestamp_field": "timestamp",
  "metric_map": {
    "water_level_cm": "water_level",
    "pressure": "pressure",
    "velocity": "velocity",
    "rainfall": "rainfall"
  },
  "station_prefix": "station"
}

Usage:
    python adapters/json_to_csv_station.py --input influx.json --mapping adapters/mapping_station_long.json --output data.csv
    python adapters/json_to_csv_station.py --input influx.ndjson --mapping adapters/mapping_station_long.json --columns data.csv
"""

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd


COMMON_RECORD_KEYS = ["records", "data", "results", "values", "series", "points"]


def warn(message):
    sys.stderr.write(message + "\n")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert station-long JSON/NDJSON into a wide CSV."
    )
    parser.add_argument("--input", required=True, help="Input JSON or NDJSON file")
    parser.add_argument("--output", default="data.csv", help="Output CSV path")
    parser.add_argument("--mapping", required=True, help="Mapping JSON file")
    parser.add_argument(
        "--columns",
        default=None,
        help="CSV file to read header from (default: data.csv if it exists)",
    )
    parser.add_argument(
        "--records-key",
        default=None,
        help="If JSON has a wrapper object, key containing the records array",
    )
    parser.add_argument(
        "--no-sort",
        action="store_true",
        help="Do not sort rows by TimeStamp",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print detected columns and sample rows without writing",
    )
    return parser.parse_args()


def load_text(path):
    return Path(path).read_text(encoding="utf-8")


def load_mapping(path):
    mapping = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(mapping, dict):
        raise ValueError("Mapping file must be a JSON object")

    station_field = mapping.get("station_field")
    timestamp_field = mapping.get("timestamp_field")
    metric_map = mapping.get("metric_map")
    station_prefix = mapping.get("station_prefix", "station")

    if not station_field or not timestamp_field:
        raise ValueError("Mapping must include station_field and timestamp_field")
    if not isinstance(metric_map, dict) or not metric_map:
        raise ValueError("Mapping must include a non-empty metric_map object")

    return station_field, timestamp_field, metric_map, station_prefix


def extract_records(payload, records_key=None):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if records_key:
            if records_key not in payload:
                raise ValueError(f"records_key '{records_key}' not found in JSON")
            records = payload[records_key]
            if not isinstance(records, list):
                raise ValueError(f"records_key '{records_key}' is not a list")
            return records
        for key in COMMON_RECORD_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return [payload]
    return []


def load_ndjson(text):
    records = []
    for idx, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            warn(f"Skipping invalid JSON at line {idx}")
            continue
        records.append(obj)
    return records


def load_records(text, records_key=None):
    stripped = text.lstrip()
    if not stripped:
        return []
    if stripped[0] in "[{":
        try:
            payload = json.loads(text)
            return extract_records(payload, records_key)
        except json.JSONDecodeError:
            return load_ndjson(text)
    return load_ndjson(text)


def load_columns(columns_path):
    path = None
    if columns_path:
        path = Path(columns_path)
    else:
        default = Path("data.csv")
        if default.exists():
            path = default
    if not path:
        return None
    header = path.read_text(encoding="utf-8").splitlines()[0]
    return [col.strip() for col in header.split(",")]


def parse_station_value(value):
    if value is None:
        raise ValueError("Record missing station value")
    if isinstance(value, bool):
        raise ValueError("Station value must be numeric or string")
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value)
    match = re.search(r"\d+", text)
    if not match:
        raise ValueError(f"Invalid station value: {value}")
    return int(match.group(0))


def build_rows(records, station_field, timestamp_field, metric_map, station_prefix):
    rows_by_ts = {}
    skipped = 0

    for record in records:
        if not isinstance(record, dict):
            skipped += 1
            continue
        if station_field not in record or timestamp_field not in record:
            skipped += 1
            continue

        station_id = parse_station_value(record.get(station_field))
        timestamp = record.get(timestamp_field)
        row = rows_by_ts.setdefault(timestamp, {"TimeStamp": timestamp})

        for src, suffix in metric_map.items():
            if src not in record:
                continue
            col = f"{station_prefix}{station_id}_{suffix}"
            row[col] = record.get(src)

    if skipped:
        warn(f"Skipped {skipped} invalid records")

    return list(rows_by_ts.values())


def format_timestamp(series):
    dt = pd.to_datetime(series, errors="coerce")
    return dt.dt.strftime("%Y-%m-%d %H:%M:%S")


def main():
    args = parse_args()
    raw_text = load_text(args.input)
    records = load_records(raw_text, args.records_key)
    if not records:
        raise ValueError("No records found in input")

    station_field, timestamp_field, metric_map, station_prefix = load_mapping(args.mapping)
    rows = build_rows(records, station_field, timestamp_field, metric_map, station_prefix)
    if not rows:
        raise ValueError("No valid records found after normalization")

    columns_from_file = load_columns(args.columns)
    if columns_from_file:
        if "TimeStamp" not in columns_from_file:
            columns = ["TimeStamp"] + columns_from_file
        else:
            columns = columns_from_file
    else:
        columns = []
        seen = set()
        for row in rows:
            for key in row.keys():
                if key not in seen:
                    columns.append(key)
                    seen.add(key)

    df = pd.DataFrame(rows, columns=columns)

    if "TimeStamp" in df.columns:
        if not args.no_sort:
            dt = pd.to_datetime(df["TimeStamp"], errors="coerce")
            df = df.assign(_ts=dt).sort_values("_ts").drop(columns="_ts")
        df["TimeStamp"] = format_timestamp(df["TimeStamp"])

    if args.dry_run:
        print("Columns:")
        print(columns)
        print("\nSample rows:")
        print(df.head(3).to_string(index=False))
        return

    output_path = Path(args.output)
    df.to_csv(output_path, index=False, encoding="utf-8")


if __name__ == "__main__":
    main()
