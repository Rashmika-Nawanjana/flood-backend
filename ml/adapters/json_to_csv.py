"""
json_to_csv.py
==============
Convert JSON/NDJSON into a CSV that matches data.csv column layout.

Usage:
    python adapters/json_to_csv.py --input influx.json --output data.csv
    python adapters/json_to_csv.py --input influx.ndjson --mapping adapters/mapping_example.json
    python adapters/json_to_csv.py --input influx.json --dry-run

Notes:
- By default, columns are read from data.csv header (if present).
- Mapping file is a JSON object of source_field -> target_column.
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


COMMON_RECORD_KEYS = ["records", "data", "results", "values", "series", "points"]
AUTO_TIMESTAMP_KEYS = ["TimeStamp", "timestamp", "time"]


def warn(message):
    sys.stderr.write(message + "\n")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert JSON/NDJSON into a CSV matching data.csv."
    )
    parser.add_argument("--input", required=True, help="Input JSON or NDJSON file")
    parser.add_argument("--output", default="data.csv", help="Output CSV path")
    parser.add_argument(
        "--columns",
        default=None,
        help="CSV file to read header from (default: data.csv if it exists)",
    )
    parser.add_argument(
        "--mapping",
        default=None,
        help="JSON mapping file (source_field -> target_column)",
    )
    parser.add_argument(
        "--timestamp-field",
        default=None,
        help="Field to use as timestamp (auto-detect if omitted)",
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
    if not path:
        return {}
    mapping = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(mapping, dict):
        raise ValueError("Mapping file must be a JSON object")
    return mapping


def apply_mapping(record, mapping):
    if not mapping:
        return record
    out = dict(record)
    for src, dst in mapping.items():
        if src in out and dst not in out:
            out[dst] = out[src]
    return out


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


def normalize_records(records, mapping):
    normalized = []
    skipped = 0
    for record in records:
        if not isinstance(record, dict):
            skipped += 1
            continue
        normalized.append(apply_mapping(record, mapping))
    if skipped:
        warn(f"Skipped {skipped} invalid records")
    return normalized


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


def detect_timestamp_field(records, explicit):
    if explicit:
        return explicit
    for key in AUTO_TIMESTAMP_KEYS:
        for record in records:
            if key in record:
                return key
    return None


def build_columns(records, columns_from_file, timestamp_field):
    if columns_from_file:
        if "TimeStamp" not in columns_from_file and timestamp_field:
            return ["TimeStamp"] + columns_from_file
        return columns_from_file

    columns = []
    seen = set()
    if timestamp_field or any("TimeStamp" in r for r in records):
        columns.append("TimeStamp")
        seen.add("TimeStamp")

    for record in records:
        for key in record.keys():
            if key not in seen:
                columns.append(key)
                seen.add(key)
    return columns


def build_rows(records, columns, timestamp_field):
    rows = []
    for record in records:
        row = {}
        if timestamp_field and "TimeStamp" not in record:
            if timestamp_field in record:
                row["TimeStamp"] = record.get(timestamp_field)
        for col in columns:
            if col in row:
                continue
            row[col] = record.get(col)
        rows.append(row)
    return rows


def format_timestamp(series):
    dt = pd.to_datetime(series, errors="coerce")
    return dt.dt.strftime("%Y-%m-%d %H:%M:%S")


def main():
    args = parse_args()
    raw_text = load_text(args.input)
    records = load_records(raw_text, args.records_key)
    if not records:
        raise ValueError("No records found in input")

    mapping = load_mapping(args.mapping)
    records = normalize_records(records, mapping)
    if not records:
        raise ValueError("No valid records found after normalization")

    timestamp_field = detect_timestamp_field(records, args.timestamp_field)
    columns_from_file = load_columns(args.columns)
    columns = build_columns(records, columns_from_file, timestamp_field)

    rows = build_rows(records, columns, timestamp_field)
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
