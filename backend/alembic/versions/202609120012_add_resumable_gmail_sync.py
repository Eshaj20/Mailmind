"""Add resumable Gmail baseline sync state.

Revision ID: 202609120012
Revises: 202608310011
Create Date: 2026-09-12
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "202609120012"
down_revision = "202608310011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "gmail_accounts",
        sa.Column("initial_sync_complete", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("gmail_accounts", sa.Column("sync_page_token", sa.Text(), nullable=True))
    op.add_column("gmail_accounts", sa.Column("sync_start_history_id", sa.String(length=128), nullable=True))
    op.add_column(
        "sync_jobs",
        sa.Column("has_more", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("sync_jobs", sa.Column("continuation_job_id", sa.Integer(), nullable=True))
    op.alter_column("gmail_accounts", "initial_sync_complete", server_default=None)
    op.alter_column("sync_jobs", "has_more", server_default=None)


def downgrade() -> None:
    op.drop_column("sync_jobs", "continuation_job_id")
    op.drop_column("sync_jobs", "has_more")
    op.drop_column("gmail_accounts", "sync_start_history_id")
    op.drop_column("gmail_accounts", "sync_page_token")
    op.drop_column("gmail_accounts", "initial_sync_complete")