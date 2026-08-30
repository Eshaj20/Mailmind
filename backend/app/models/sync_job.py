from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

# The SyncJob class represents a synchronization job for a user's Gmail account. It is used to track the status and progress of email synchronization tasks, including the number of attempts, synced emails, created and updated counts, and any errors encountered during the process. 

# The class includes fields for user ID, Gmail account ID, job type, status, attempt count, maximum attempts, per-job Gmail fetch limit, synced count, created count, updated count, Celery task ID, error type, error message, start and finish timestamps, and creation and update timestamps. It establishes relationships with the User and GmailAccount models for easy access to related data.
class SyncJob(Base):
    __tablename__ = "sync_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    gmail_account_id: Mapped[int] = mapped_column(ForeignKey("gmail_accounts.id", ondelete="CASCADE"), index=True)
    job_type: Mapped[str] = mapped_column(String(32), default="gmail_sync", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    max_results: Mapped[int] = mapped_column(Integer, default=25, nullable=False)
    synced_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    celery_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    gmail_account = relationship("GmailAccount")
