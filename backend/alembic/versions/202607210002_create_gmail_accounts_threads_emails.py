"""create gmail accounts threads and emails

Revision ID: 202607210002
Revises: 202607140001
Create Date: 2026-07-21
"""
from alembic import op
import sqlalchemy as sa

revision = "202607210002"
down_revision = "202607140001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gmail_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("google_email", sa.String(length=320), nullable=False),
        sa.Column("refresh_token_ciphertext", sa.Text(), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=True),
        sa.Column("history_id", sa.String(length=128), nullable=True),
        sa.Column("sync_status", sa.String(length=32), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "google_email", name="uq_gmail_accounts_user_email"),
    )
    op.create_index(op.f("ix_gmail_accounts_id"), "gmail_accounts", ["id"], unique=False)
    op.create_index(op.f("ix_gmail_accounts_user_id"), "gmail_accounts", ["user_id"], unique=False)

    op.create_table(
        "threads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("gmail_account_id", sa.Integer(), nullable=False),
        sa.Column("gmail_thread_id", sa.String(length=128), nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["gmail_account_id"], ["gmail_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gmail_account_id", "gmail_thread_id", name="uq_threads_account_thread"),
    )
    op.create_index(op.f("ix_threads_gmail_account_id"), "threads", ["gmail_account_id"], unique=False)
    op.create_index(op.f("ix_threads_id"), "threads", ["id"], unique=False)
    op.create_index(op.f("ix_threads_user_id"), "threads", ["user_id"], unique=False)

    op.create_table(
        "emails",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("gmail_account_id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column("gmail_message_id", sa.String(length=128), nullable=False),
        sa.Column("sender", sa.String(length=512), nullable=True),
        sa.Column("recipients", sa.Text(), nullable=True),
        sa.Column("subject", sa.String(length=512), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("body_preview", sa.Text(), nullable=True),
        sa.Column("labels", sa.JSON(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["gmail_account_id"], ["gmail_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["thread_id"], ["threads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gmail_account_id", "gmail_message_id", name="uq_emails_account_message"),
    )
    op.create_index(op.f("ix_emails_gmail_account_id"), "emails", ["gmail_account_id"], unique=False)
    op.create_index(op.f("ix_emails_id"), "emails", ["id"], unique=False)
    op.create_index(op.f("ix_emails_thread_id"), "emails", ["thread_id"], unique=False)
    op.create_index(op.f("ix_emails_user_id"), "emails", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_emails_user_id"), table_name="emails")
    op.drop_index(op.f("ix_emails_thread_id"), table_name="emails")
    op.drop_index(op.f("ix_emails_id"), table_name="emails")
    op.drop_index(op.f("ix_emails_gmail_account_id"), table_name="emails")
    op.drop_table("emails")
    op.drop_index(op.f("ix_threads_user_id"), table_name="threads")
    op.drop_index(op.f("ix_threads_id"), table_name="threads")
    op.drop_index(op.f("ix_threads_gmail_account_id"), table_name="threads")
    op.drop_table("threads")
    op.drop_index(op.f("ix_gmail_accounts_user_id"), table_name="gmail_accounts")
    op.drop_index(op.f("ix_gmail_accounts_id"), table_name="gmail_accounts")
    op.drop_table("gmail_accounts")
