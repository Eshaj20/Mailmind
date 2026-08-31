"""Add cleanup action undo log.

Revision ID: 202608310010
Revises: 202608300009
Create Date: 2026-08-31
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "202608310010"
down_revision = "202608300009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cleanup_action_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("email_id", sa.Integer(), nullable=False),
        sa.Column("gmail_account_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("gmail_message_id", sa.String(length=128), nullable=False),
        sa.Column("previous_labels", sa.JSON(), nullable=True),
        sa.Column("previous_is_read", sa.Boolean(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("undone_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["email_id"], ["emails.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["gmail_account_id"], ["gmail_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cleanup_action_logs_id"), "cleanup_action_logs", ["id"], unique=False)
    op.create_index(op.f("ix_cleanup_action_logs_user_id"), "cleanup_action_logs", ["user_id"], unique=False)
    op.create_index(op.f("ix_cleanup_action_logs_email_id"), "cleanup_action_logs", ["email_id"], unique=False)
    op.create_index(op.f("ix_cleanup_action_logs_gmail_account_id"), "cleanup_action_logs", ["gmail_account_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_cleanup_action_logs_gmail_account_id"), table_name="cleanup_action_logs")
    op.drop_index(op.f("ix_cleanup_action_logs_email_id"), table_name="cleanup_action_logs")
    op.drop_index(op.f("ix_cleanup_action_logs_user_id"), table_name="cleanup_action_logs")
    op.drop_index(op.f("ix_cleanup_action_logs_id"), table_name="cleanup_action_logs")
    op.drop_table("cleanup_action_logs")