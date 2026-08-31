"""Add email spam detection fields.

Revision ID: 202608310011
Revises: 202608310010
Create Date: 2026-08-31
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "202608310011"
down_revision = "202608310010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("emails", sa.Column("spam_label", sa.String(length=16), nullable=True))
    op.add_column("emails", sa.Column("spam_score", sa.Float(), nullable=True))
    op.add_column("emails", sa.Column("spam_model_version", sa.String(length=64), nullable=True))
    op.add_column("emails", sa.Column("spam_detected_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_emails_spam_label"), "emails", ["spam_label"], unique=False)
    op.create_index(op.f("ix_emails_spam_score"), "emails", ["spam_score"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_emails_spam_score"), table_name="emails")
    op.drop_index(op.f("ix_emails_spam_label"), table_name="emails")
    op.drop_column("emails", "spam_detected_at")
    op.drop_column("emails", "spam_model_version")
    op.drop_column("emails", "spam_score")
    op.drop_column("emails", "spam_label")