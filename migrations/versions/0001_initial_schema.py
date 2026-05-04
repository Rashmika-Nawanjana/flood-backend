"""Initial flood monitoring schema.

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-05-03 00:00:00.000000

Loads schema from migrations/sql/0001_initial_schema.sql
"""
from __future__ import annotations

import os

from alembic import op

revision = "0001_initial_schema"
down_revision = None


def _exec_sql_file(filename: str) -> None:
    """Load and execute a SQL file from migrations/sql/."""
    here = os.path.dirname(__file__)
    sql_path = os.path.join(here, "..", "sql", filename)
    with open(sql_path, "r", encoding="utf-8") as fh:
        sql = fh.read()
        op.execute(sql)


def upgrade() -> None:
    """Apply initial schema from SQL file."""
    _exec_sql_file("0001_initial_schema.sql")


def downgrade() -> None:
    """Downgrade not implemented for initial schema."""
    raise NotImplementedError("Downgrade from initial schema not supported; recreate database.")
