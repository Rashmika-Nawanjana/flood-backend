from __future__ import annotations

from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings


def get_connection() -> psycopg.Connection:
    dsn = settings.database_url
    # psycopg.connect does not accept SQLAlchemy driver suffixes.
    if dsn.startswith("postgresql+psycopg://"):
        dsn = dsn.replace("postgresql+psycopg://", "postgresql://", 1)
    return psycopg.connect(dsn, row_factory=dict_row)


def connection_ctx() -> Iterator[psycopg.Connection]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
