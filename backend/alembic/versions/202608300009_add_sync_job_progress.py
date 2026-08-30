"""Add sync job progress fields.

Revision ID: 202608300009
Revises: 202608300008
Create Date: 2026-08-30
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "202608300009"
down_revision = "202608300008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sync_jobs",
        sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("sync_jobs", "processed_count", server_default=None)


def downgrade() -> None:
    op.drop_column("sync_jobs", "processed_count")