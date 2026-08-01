"""create sync jobs

Revision ID: 202608010003
Revises: 202607210002
Create Date: 2026-08-01
"""
from alembic import op
import sqlalchemy as sa

revision = "202608010003"
down_revision = "202607210002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sync_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("gmail_account_id", sa.Integer(), nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("synced_count", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("celery_task_id", sa.String(length=128), nullable=True),
        sa.Column("error_type", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["gmail_account_id"], ["gmail_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sync_jobs_gmail_account_id"), "sync_jobs", ["gmail_account_id"], unique=False)
    op.create_index(op.f("ix_sync_jobs_id"), "sync_jobs", ["id"], unique=False)
    op.create_index(op.f("ix_sync_jobs_status"), "sync_jobs", ["status"], unique=False)
    op.create_index(op.f("ix_sync_jobs_user_id"), "sync_jobs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sync_jobs_user_id"), table_name="sync_jobs")
    op.drop_index(op.f("ix_sync_jobs_status"), table_name="sync_jobs")
    op.drop_index(op.f("ix_sync_jobs_id"), table_name="sync_jobs")
    op.drop_index(op.f("ix_sync_jobs_gmail_account_id"), table_name="sync_jobs")
    op.drop_table("sync_jobs")
