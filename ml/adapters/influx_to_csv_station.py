"""
influx_to_csv_station.py
=========================
Query InfluxDB and write a wide CSV matching data.csv for station-long data.

Usage:
    python adapters/influx_to_csv_station.py \
        --mapping adapters/mapping_station_long.json \
        --output data.csv \
        --bucket flood-bucket \
        --org flood-org \
        --measurement flood_metrics \
        --start -24h
"""

import argparse
import io
import os
import sys
from pathlib import Path

import pandas as pd
import requests

from json_to_csv_station import build_rows, format_timestamp, load_columns, load_mapping


def warn(message):
    sys.stderr.write(message + "\n")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Query InfluxDB and output a wide CSV for station-long data."
    )
    parser.add_argument("--url", default=os.getenv("INFLUXDB_URL", "http://localhost:8086"))
    parser.add_argument("--org", default=os.getenv("INFLUXDB_ORG"))
    parser.add_argument("--token", default=os.getenv("INFLUXDB_TOKEN"))
    parser.add_argument("--bucket", default=os.getenv("INFLUXDB_BUCKET"))
    parser.add_argument("--measurement", default=os.getenv("INFLUXDB_MEASUREMENT"))
    parser.add_argument("--start", default=os.getenv("INFLUXDB_START", "-24h"))
    parser.add_argument("--stop", default=os.getenv("INFLUXDB_STOP"))
    parser.add_argument("--station-tag", default=os.getenv("INFLUXDB_STATION_TAG"))
    parser.add_argument("--fields", default=os.getenv("INFLUXDB_FIELDS"))
    parser.add_argument("--time-column", default=os.getenv("INFLUXDB_TIME_COLUMN", "_time"))
    parser.add_argument("--query", default=None, help="Raw Flux query to run")
    parser.add_argument("--mapping", required=True, help="Mapping JSON file")
    parser.add_argument("--output", default="data.csv", help="Output CSV path")
    parser.add_argument(
        "--columns",
        default=None,
        help="CSV file to read header from (default: data.csv if it exists)",
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


def parse_fields(value, metric_map):
    if value:
        return [item.strip() for item in value.split(",") if item.strip()]
    return list(metric_map.keys())


def build_flux_query(bucket, measurement, start, stop, station_tag, fields):
    if not bucket:
        raise ValueError("--bucket is required unless --query is provided")
    if not start:
        raise ValueError("--start is required unless --query is provided")
    if not fields:
        raise ValueError("No fields selected for query")

    field_filter = " or ".join([f'r["_field"] == "{field}"' for field in fields])
    stop_clause = f", stop: {stop}" if stop else ""

    query = [
        f'from(bucket: "{bucket}")',
        f"  |> range(start: {start}{stop_clause})",
    ]

    if measurement:
        query.append(f'  |> filter(fn: (r) => r["_measurement"] == "{measurement}")')

    query.append(f"  |> filter(fn: (r) => {field_filter})")
    query.append(
        "  |> pivot(rowKey:[\"_time\",\"%s\"], columnKey:[\"_field\"], valueColumn:\"_value\")"
        % station_tag
    )
    keep_cols = ",".join([f'"{field}"' for field in fields])
    query.append(f"  |> keep(columns: [\"_time\",\"{station_tag}\",{keep_cols}])")
    query.append("  |> sort(columns: [\"_time\"])")

    return "\n".join(query)


def query_influx_csv(url, org, token, query):
    if not url:
        raise ValueError("InfluxDB url is required")
    if not org:
        raise ValueError("InfluxDB org is required")

    endpoint = url.rstrip("/") + "/api/v2/query"
    headers = {
        "Accept": "application/csv",
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Token {token}"

    payload = {
        "query": query,
        "type": "flux",
        "dialect": {"annotations": []},
    }

    response = requests.post(
        endpoint,
        params={"org": org},
        json=payload,
        headers=headers,
        timeout=60,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        snippet = response.text[:500]
        raise SystemExit(
            f"Influx query failed ({response.status_code}): {snippet}"
        ) from exc

    return response.text


def load_frame(csv_text):
    if not csv_text.strip():
        raise ValueError("Influx query returned empty response")
    df = pd.read_csv(io.StringIO(csv_text), comment="#")
    if df.empty:
        return df
    drop_cols = [col for col in ("result", "table") if col in df.columns]
    if drop_cols:
        df = df.drop(columns=drop_cols)
    return df


def main():
    args = parse_args()

    station_field, timestamp_field, metric_map, station_prefix = load_mapping(args.mapping)
    station_tag = args.station_tag or station_field
    fields = parse_fields(args.fields, metric_map)

    if args.query:
        flux_query = args.query
    else:
        flux_query = build_flux_query(
            bucket=args.bucket,
            measurement=args.measurement,
            start=args.start,
            stop=args.stop,
            station_tag=station_tag,
            fields=fields,
        )

    csv_text = query_influx_csv(args.url, args.org, args.token, flux_query)
    df = load_frame(csv_text)
    if df.empty:
        raise ValueError("No rows returned from InfluxDB query")

    time_col = args.time_column
    missing_cols = [col for col in [station_tag, time_col] if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Influx result missing required columns: {missing_cols}")

    missing_fields = [field for field in fields if field not in df.columns]
    if missing_fields:
        raise ValueError(f"Influx result missing fields: {missing_fields}")

    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    if df[time_col].isna().any():
        warn("Some timestamps could not be parsed and will be skipped")
        df = df.dropna(subset=[time_col])

    records = []
    for _, row in df.iterrows():
        record = {
            station_field: row[station_tag],
            timestamp_field: row[time_col],
        }
        for field in fields:
            record[field] = row.get(field)
        records.append(record)

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

    out = pd.DataFrame(rows, columns=columns)

    if "TimeStamp" in out.columns:
        if not args.no_sort:
            dt = pd.to_datetime(out["TimeStamp"], errors="coerce")
            out = out.assign(_ts=dt).sort_values("_ts").drop(columns="_ts")
        out["TimeStamp"] = format_timestamp(out["TimeStamp"])

    if args.dry_run:
        print("Columns:")
        print(columns)
        print("\nSample rows:")
        print(out.head(3).to_string(index=False))
        return

    output_path = Path(args.output)
    out.to_csv(output_path, index=False, encoding="utf-8")


if __name__ == "__main__":
    main()
