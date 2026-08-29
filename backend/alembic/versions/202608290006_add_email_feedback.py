"""add email feedback

Revision ID: 202608290006
Revises: 202608250005
Create Date: 2026-08-29 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202608290006"
down_revision: str | None = "202608250005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_feedback",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("feedback_type", sa.String(length=32), nullable=False),
        sa.Column("original_category", sa.String(length=32), nullable=True),
        sa.Column("corrected_category", sa.String(length=32), nullable=True),
        sa.Column("original_priority", sa.String(length=16), nullable=True),
        sa.Column("corrected_priority", sa.String(length=16), nullable=True),
        sa.Column("original_needs_reply", sa.Boolean(), nullable=True),
        sa.Column("corrected_needs_reply", sa.Boolean(), nullable=True),
        sa.Column("original_confidence", sa.Float(), nullable=True),
        sa.Column("model_version", sa.String(length=64), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["email_id"], ["emails.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_email_feedback_id"), "email_feedback", ["id"], unique=False)
    op.create_index(op.f("ix_email_feedback_email_id"), "email_feedback", ["email_id"], unique=False)
    op.create_index(op.f("ix_email_feedback_user_id"), "email_feedback", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_email_feedback_user_id"), table_name="email_feedback")
    op.drop_index(op.f("ix_email_feedback_email_id"), table_name="email_feedback")
    op.drop_index(op.f("ix_email_feedback_id"), table_name="email_feedback")
    op.drop_table("email_feedback")