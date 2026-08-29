from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class AIUsageLog(Base):
    """Per-user AI usage ledger for cost and token observability.

    The app can run with local/rule-based fallbacks, so usage is estimated from
    text length today. If a provider returns exact usage later, the same table
    can store those exact token counts without changing dashboard/report APIs.
    """

    __tablename__ = "ai_usage_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    email_id: Mapped[int | None] = mapped_column(ForeignKey("emails.id", ondelete="SET NULL"), nullable=True, index=True)
    thread_id: Mapped[int | None] = mapped_column(ForeignKey("threads.id", ondelete="SET NULL"), nullable=True, index=True)
    feature: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    user = relationship("User")
    email = relationship("Email")
    thread = relationship("EmailThread")