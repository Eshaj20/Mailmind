from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class EmailFeedback(Base):
    """User correction/approval history for an email-level AI decision.

    The latest prediction lives on `emails` for fast dashboard reads, while this
    append-only table records human feedback so future evaluation and retraining
    can compare model output against user-approved labels.
    """

    __tablename__ = "email_feedback"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    feedback_type: Mapped[str] = mapped_column(String(32), default="correction", nullable=False)
    original_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    corrected_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    original_priority: Mapped[str | None] = mapped_column(String(16), nullable=True)
    corrected_priority: Mapped[str | None] = mapped_column(String(16), nullable=True)
    original_needs_reply: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    corrected_needs_reply: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    original_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    email = relationship("Email", back_populates="feedback")
    user = relationship("User")