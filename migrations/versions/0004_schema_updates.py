"""Compatibility shim for the legacy 0004_schema_updates revision.

Revision ID: 0004_schema_updates
Revises: 0004_add_zone_id_to_users
Create Date: 2026-05-06 00:00:00.000000
"""
from __future__ import annotations

revision = "0004_schema_updates"
down_revision = "0004_add_zone_id_to_users"


def upgrade() -> None:
    """No-op shim to preserve Alembic history compatibility."""


def downgrade() -> None:
    """No-op shim to preserve Alembic history compatibility."""
