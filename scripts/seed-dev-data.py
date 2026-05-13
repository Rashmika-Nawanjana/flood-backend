#!/usr/bin/env python
"""Reset and seed a coherent Mahaweli-based dev dataset for Postgres."""

from __future__ import annotations

import os
from pathlib import Path
import psycopg
from dotenv import load_dotenv


LEGACY_TABLES = [
    "alert_events",
    "anomalies",
    "flood_predictions",
    "sensor_nodes",
    "zone_shelters",
    "zones",
    "users",
    "model_metadata",
    "rivers",
    "station",
    "sensors",
    "shelters",
    "evacuation_routes",
    "historical_floods",
]


def _get_database_url() -> str:
    # Always load .env from repository root (one level up from scripts/)
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)
    url = os.getenv("DATABASE_URL")
    if url:
        return url.replace("postgresql+psycopg://", "postgresql://")

    user = os.getenv("POSTGRES_USER", "admin")
    password = os.getenv("POSTGRES_PASSWORD", "admin")
    database = os.getenv("POSTGRES_DB", "flooddb")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def _table_exists(conn: psycopg.Connection, table_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s)", (table_name,))
        row = cur.fetchone()
    return bool(row and row[0])


def _truncate_all_public_tables(conn: psycopg.Connection) -> None:
    # Fetch all user-defined tables in public schema and truncate them to avoid FK conflicts.
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """
        )
        rows = cur.fetchall()
    tables = [r[0] for r in rows if r and r[0]]
    if not tables:
        return
    quoted = ", ".join(f'"{name}"' for name in tables)
    conn.execute(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE")


def _run_seed_sql(conn: psycopg.Connection, seed_sql: str) -> None:
    for statement in seed_sql.split(";"):
        sql = statement.strip()
        if sql:
            conn.execute(sql)

def seed() -> int:
    # Hardcode seed SQL path to scripts/seed.sql (same directory as this script)
    seed_file = Path(__file__).with_name("seed.sql")

    if not seed_file.exists():
        print(f"ERROR: Seed file not found: {seed_file}")
        return 1

    seed_sql = seed_file.read_text(encoding="utf-8")

    db_url = _get_database_url()

    try:
        with psycopg.connect(db_url) as conn:
            # Always truncate all public tables to avoid conflicts
            _truncate_all_public_tables(conn)
            _run_seed_sql(conn, seed_sql)
            conn.commit()

        print("OK: Mahaweli seed data inserted cleanly")
        print(f"   Seed file: {seed_file}")
        return 0
    except Exception as exc:
        print(f"ERROR: Seeding failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(seed())
