from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

# The User class represents a user in the application. It defines the structure of the users table in the database, including fields for user ID, email, full name, hashed password, active status, and creation timestamp.

#  The class also establishes a relationship with the GmailAccount model to facilitate querying and data retrieval related to a user's Gmail accounts.
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    gmail_accounts = relationship("GmailAccount", back_populates="user", cascade="all, delete-orphan")
