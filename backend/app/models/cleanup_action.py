from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

CleanupActionName = Literal["archive", "mark_read"]


class CleanupActionLog(Base):
    """Audit record for reversible cleanup actions.

    Each row captures the email state before Gmail was modified. This lets the
    user undo archive/mark-read actions without trusting the AI suggestion blindly.
    """

    __tablename__ = "cleanup_action_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id", ondelete="CASCADE"), index=True)
    gmail_account_id: Mapped[int] = mapped_column(ForeignKey("gmail_accounts.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    gmail_message_id: Mapped[str] = mapped_column(String(128), nullable=False)
    previous_labels: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    previous_is_read: Mapped[bool] = mapped_column(Boolean, nullable=False)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User")
    email = relationship("Email")
    gmail_account = relationship("GmailAccount")