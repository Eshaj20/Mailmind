from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

# The EmailClassification class represents an append-only log of every classification run for an email. It is used to store the full history of email classifications, allowing for auditing and reprocessing of confidence drift and model versions. The class includes fields for email ID, user ID, category, priority, needs reply flag, confidence score, stage, model version, rationale, and creation timestamp. It establishes relationships with the Email and User models for easy access to related data.

class EmailClassification(Base):
    """Append-only log of every classification run for an email.

    `Email` keeps a denormalized snapshot of the latest result for fast reads
    (dashboard, filtering); this table keeps the full history so confidence
    drift and model versions can be audited or reprocessed later.
    """

    __tablename__ = "email_classifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    needs_reply: Mapped[bool] = mapped_column(nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    stage: Mapped[str] = mapped_column(String(16), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    email = relationship("Email", back_populates="classifications")
    user = relationship("User")
