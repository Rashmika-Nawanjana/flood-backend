"""Add users table for Clerk webhook sync.

Revision ID: 0003_users_table
Revises: 0002_zone_model
Create Date: 2026-05-05 00:00:00.000000

Loads schema from migrations/sql/0003_users_table.sql
"""
from __future__ import annotations

import os

from alembic import op

revision = "0003_users_table"
down_revision = "0002_zone_model"


def _exec_sql_file(filename: str) -> None:
    """Load and execute a SQL file from migrations/sql/."""
    here = os.path.dirname(__file__)
    sql_path = os.path.join(here, "..", "sql", filename)
    with open(sql_path, "r", encoding="utf-8") as fh:
        sql = fh.read()
        op.execute(sql)


def upgrade() -> None:
    """Apply users table schema from SQL file."""
    _exec_sql_file("0003_users_table.sql")


def downgrade() -> None:
    """Downgrade not implemented for this migration."""
    raise NotImplementedError("Downgrade for 0003_users_table is not implemented.")
