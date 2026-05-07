"""Update rivers linkage and flood predictions schema.

Revision ID: 0004_schema_updates
Revises: 0003_users_table
Create Date: 2026-05-06 00:00:00.000000

Loads schema from migrations/sql/0004_schema_updates.sql
"""
from __future__ import annotations

import os

from alembic import op

revision = "0004_schema_updates"
down_revision = "0003_users_table"


def _exec_sql_file(filename: str) -> None:
    """Load and execute a SQL file from migrations/sql/."""
    here = os.path.dirname(__file__)
    sql_path = os.path.join(here, "..", "sql", filename)
    with open(sql_path, "r", encoding="utf-8") as fh:
        sql = fh.read()
        op.execute(sql)


def upgrade() -> None:
    """Apply schema updates from SQL file."""
    _exec_sql_file("0004_schema_updates.sql")


def downgrade() -> None:
    """Downgrade not implemented for this migration."""
    raise NotImplementedError("Downgrade for 0004_schema_updates is not implemented.")
