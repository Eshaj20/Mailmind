"""Add per-job Gmail sync limit.

Revision ID: 202608300008
Revises: 202608290007
Create Date: 2026-08-30
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "202608300008"
down_revision = "202608290007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sync_jobs",
        sa.Column("max_results", sa.Integer(), nullable=False, server_default="25"),
    )
    op.alter_column("sync_jobs", "max_results", server_default=None)


def downgrade() -> None:
    op.drop_column("sync_jobs", "max_results")