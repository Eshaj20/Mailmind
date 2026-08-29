from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.feedback import EmailFeedback
from app.models.gmail import Email
from app.models.user import User


@dataclass(frozen=True)
class FeedbackResult:
    feedback: EmailFeedback
    email: Email


def record_email_feedback(
    db: Session,
    user: User,
    *,
    email_id: int,
    feedback_type: str,
    corrected_category: str | None,
    corrected_priority: str | None,
    corrected_needs_reply: bool | None,
    note: str | None = None,
) -> FeedbackResult | None:
    """Persist user feedback and update the email's latest AI label snapshot."""
    email = db.scalar(select(Email).where(Email.id == email_id, Email.user_id == user.id))
    if email is None:
        return None

    feedback = EmailFeedback(
        email_id=email.id,
        user_id=user.id,
        feedback_type=feedback_type,
        original_category=email.category,
        corrected_category=corrected_category,
        original_priority=email.priority,
        corrected_priority=corrected_priority,
        original_needs_reply=email.needs_reply,
        corrected_needs_reply=corrected_needs_reply,
        original_confidence=email.classification_confidence,
        model_version=email.classification_model_version,
        note=note,
    )
    db.add(feedback)

    if corrected_category is not None:
        email.category = corrected_category
    if corrected_priority is not None:
        email.priority = corrected_priority
    if corrected_needs_reply is not None:
        email.needs_reply = corrected_needs_reply

    db.flush()
    return FeedbackResult(feedback=feedback, email=email)