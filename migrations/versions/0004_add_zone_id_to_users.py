"""Add zone_id foreign key to users table.

Revision ID: 0004_add_zone_id_to_users
Revises: 0003_users_table
Create Date: 2026-05-07 00:00:00.000000

Loads schema from migrations/sql/0004_add_zone_id_to_users.sql
"""
from __future__ import annotations

import os

from alembic import op

revision = "0004_add_zone_id_to_users"
down_revision = "0003_users_table"


def _exec_sql_file(filename: str) -> None:
    """Load and execute a SQL file from migrations/sql/."""
    here = os.path.dirname(__file__)
    sql_path = os.path.join(here, "..", "sql", filename)
    with open(sql_path, "r", encoding="utf-8") as fh:
        sql = fh.read()
        op.execute(sql)


def upgrade() -> None:
    """Add zone_id column and foreign key to users table."""
    _exec_sql_file("0004_add_zone_id_to_users.sql")


def downgrade() -> None:
    """Remove zone_id column from users table."""
    op.execute("DROP INDEX IF EXISTS idx_users_zone_id;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS zone_id;")
