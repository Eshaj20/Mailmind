"""add ai usage logs

Revision ID: 202608290007
Revises: 202608290006
Create Date: 2026-08-29 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202608290007"
down_revision: str | None = "202608290006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("email_id", sa.Integer(), nullable=True),
        sa.Column("thread_id", sa.Integer(), nullable=True),
        sa.Column("feature", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["email_id"], ["emails.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["thread_id"], ["threads.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_usage_logs_email_id"), "ai_usage_logs", ["email_id"], unique=False)
    op.create_index(op.f("ix_ai_usage_logs_feature"), "ai_usage_logs", ["feature"], unique=False)
    op.create_index(op.f("ix_ai_usage_logs_id"), "ai_usage_logs", ["id"], unique=False)
    op.create_index(op.f("ix_ai_usage_logs_thread_id"), "ai_usage_logs", ["thread_id"], unique=False)
    op.create_index(op.f("ix_ai_usage_logs_user_id"), "ai_usage_logs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_usage_logs_user_id"), table_name="ai_usage_logs")
    op.drop_index(op.f("ix_ai_usage_logs_thread_id"), table_name="ai_usage_logs")
    op.drop_index(op.f("ix_ai_usage_logs_id"), table_name="ai_usage_logs")
    op.drop_index(op.f("ix_ai_usage_logs_feature"), table_name="ai_usage_logs")
    op.drop_index(op.f("ix_ai_usage_logs_email_id"), table_name="ai_usage_logs")
    op.drop_table("ai_usage_logs")