"""Add zone-centric model migration.

Revision ID: 0002_zone_model
Revises: 0001_initial_schema
Create Date: 2026-05-04 00:00:00.000000

Loads schema from migrations/sql/0002_zone_model.sql
"""
from __future__ import annotations

import os

from alembic import op

revision = "0002_zone_model"
down_revision = "0001_initial_schema"


def _exec_sql_file(filename: str) -> None:
    """Load and execute a SQL file from migrations/sql/."""
    here = os.path.dirname(__file__)
    sql_path = os.path.join(here, "..", "sql", filename)
    with open(sql_path, "r", encoding="utf-8") as fh:
        sql = fh.read()
        op.execute(sql)


def upgrade() -> None:
    """Apply zone model schema from SQL file."""
    _exec_sql_file("0002_zone_model.sql")


def downgrade() -> None:
    """Downgrade not implemented for this migration."""
    raise NotImplementedError("Downgrade for 0002_zone_model is not implemented.")
