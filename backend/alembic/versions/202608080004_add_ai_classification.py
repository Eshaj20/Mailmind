"""add ai classification

Revision ID: 202608080004
Revises: 202608010003
Create Date: 2026-08-08
"""
from alembic import op
import sqlalchemy as sa

revision = "202608080004"
down_revision = "202608010003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("emails", sa.Column("category", sa.String(length=32), nullable=True))
    op.add_column("emails", sa.Column("priority", sa.String(length=16), nullable=True))
    op.add_column("emails", sa.Column("needs_reply", sa.Boolean(), nullable=True))
    op.add_column("emails", sa.Column("classification_confidence", sa.Float(), nullable=True))
    op.add_column("emails", sa.Column("classification_model_version", sa.String(length=64), nullable=True))
    op.add_column("emails", sa.Column("classified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_emails_category"), "emails", ["category"], unique=False)
    op.create_index(op.f("ix_emails_priority"), "emails", ["priority"], unique=False)
    op.create_index(op.f("ix_emails_classified_at"), "emails", ["classified_at"], unique=False)

    op.add_column("threads", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("threads", sa.Column("summary_model_version", sa.String(length=64), nullable=True))
    op.add_column("threads", sa.Column("summarized_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "email_classifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("needs_reply", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("stage", sa.String(length=16), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["email_id"], ["emails.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_email_classifications_email_id"), "email_classifications", ["email_id"], unique=False
    )
    op.create_index(
        op.f("ix_email_classifications_id"), "email_classifications", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_email_classifications_user_id"), "email_classifications", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_email_classifications_user_id"), table_name="email_classifications")
    op.drop_index(op.f("ix_email_classifications_id"), table_name="email_classifications")
    op.drop_index(op.f("ix_email_classifications_email_id"), table_name="email_classifications")
    op.drop_table("email_classifications")

    op.drop_column("threads", "summarized_at")
    op.drop_column("threads", "summary_model_version")
    op.drop_column("threads", "summary")

    op.drop_index(op.f("ix_emails_classified_at"), table_name="emails")
    op.drop_index(op.f("ix_emails_priority"), table_name="emails")
    op.drop_index(op.f("ix_emails_category"), table_name="emails")
    op.drop_column("emails", "classified_at")
    op.drop_column("emails", "classification_model_version")
    op.drop_column("emails", "classification_confidence")
    op.drop_column("emails", "needs_reply")
    op.drop_column("emails", "priority")
    op.drop_column("emails", "category")
