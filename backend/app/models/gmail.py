from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class GmailAccount(Base):
    __tablename__ = "gmail_accounts"
    __table_args__ = (UniqueConstraint("user_id", "google_email", name="uq_gmail_accounts_user_email"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    google_email: Mapped[str] = mapped_column(String(320), nullable=False)
    refresh_token_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    history_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sync_status: Mapped[str] = mapped_column(String(32), default="connected", nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    user = relationship("User", back_populates="gmail_accounts")
    threads = relationship("EmailThread", back_populates="gmail_account", cascade="all, delete-orphan")
    emails = relationship("Email", back_populates="gmail_account", cascade="all, delete-orphan")


class EmailThread(Base):
    __tablename__ = "threads"
    __table_args__ = (UniqueConstraint("gmail_account_id", "gmail_thread_id", name="uq_threads_account_thread"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    gmail_account_id: Mapped[int] = mapped_column(ForeignKey("gmail_accounts.id", ondelete="CASCADE"), index=True)
    gmail_thread_id: Mapped[str] = mapped_column(String(128), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    user = relationship("User")
    gmail_account = relationship("GmailAccount", back_populates="threads")
    emails = relationship("Email", back_populates="thread", cascade="all, delete-orphan")


class Email(Base):
    __tablename__ = "emails"
    __table_args__ = (UniqueConstraint("gmail_account_id", "gmail_message_id", name="uq_emails_account_message"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    gmail_account_id: Mapped[int] = mapped_column(ForeignKey("gmail_accounts.id", ondelete="CASCADE"), index=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id", ondelete="CASCADE"), index=True)
    gmail_message_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sender: Mapped[str | None] = mapped_column(String(512), nullable=True)
    recipients: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    labels: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    is_read: Mapped[bool] = mapped_column(default=False, nullable=False)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    user = relationship("User")
    gmail_account = relationship("GmailAccount", back_populates="emails")
    thread = relationship("EmailThread", back_populates="emails")
