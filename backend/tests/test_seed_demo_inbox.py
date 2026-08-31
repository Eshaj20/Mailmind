from sqlalchemy import select

from app.models.classification import EmailClassification
from app.models.cleanup_action import CleanupActionLog
from app.models.gmail import Email, GmailAccount
from app.models.sync_job import SyncJob
from app.models.user import User
from app.services.cleanup_actions import apply_cleanup_action, undo_cleanup_action
from scripts.seed_demo_inbox import DEMO_EMAIL, DEMO_PASSWORD, seed_demo_inbox


def test_seed_demo_inbox_creates_classified_searchable_demo_data(db_session):
    result = seed_demo_inbox(db_session, count=20, reset=True)

    user = db_session.scalar(select(User).where(User.email == DEMO_EMAIL))
    emails = list(db_session.scalars(select(Email).where(Email.user_id == user.id)))
    classifications = list(db_session.scalars(select(EmailClassification).where(EmailClassification.user_id == user.id)))
    account = db_session.scalar(select(GmailAccount).where(GmailAccount.user_id == user.id))
    sync_job = db_session.scalar(select(SyncJob).where(SyncJob.user_id == user.id, SyncJob.job_type == "demo_seed"))

    assert result["email"] == DEMO_EMAIL
    assert result["password"] == DEMO_PASSWORD
    assert len(emails) == 20
    assert len(classifications) == 20
    assert account.google_email == "demo.inbox@mailmind.dev"
    assert sync_job.status == "succeeded"
    assert sync_job.max_results == 20
    assert all(email.search_text for email in emails)
    assert all(email.search_embedding for email in emails)
    assert {email.category for email in emails}.issubset({"primary", "promotions", "social", "updates", "spam"})


def test_seed_demo_inbox_is_idempotent_without_reset(db_session):
    first = seed_demo_inbox(db_session, count=12, reset=True)
    second = seed_demo_inbox(db_session, count=12, reset=False)
    user = db_session.scalar(select(User).where(User.email == DEMO_EMAIL))
    emails = list(db_session.scalars(select(Email).where(Email.user_id == user.id)))

    assert first["created_count"] == 12
    assert second["created_count"] == 0
    assert len(emails) == 12

class DemoCleanupClient:
    def refresh_access_token(self, refresh_token: str) -> str:
        raise AssertionError("demo cleanup must not call real Gmail token refresh")

    def modify_message_labels(self, *args, **kwargs):
        raise AssertionError("demo cleanup must not call real Gmail modify API")


def test_demo_cleanup_and_undo_are_local_only(db_session):
    seed_demo_inbox(db_session, count=5, reset=True)
    user = db_session.scalar(select(User).where(User.email == DEMO_EMAIL))
    email = db_session.scalar(select(Email).where(Email.user_id == user.id, Email.labels.contains(["INBOX"])))

    result = apply_cleanup_action(
        db_session,
        user,
        DemoCleanupClient(),
        email_ids=[email.id],
        action="archive",
    )
    db_session.commit()

    assert result.applied_count == 1
    assert len(result.action_ids) == 1
    db_session.refresh(email)
    assert "INBOX" not in email.labels
    assert db_session.scalar(select(CleanupActionLog).where(CleanupActionLog.id == result.action_ids[0])) is not None

    undo = undo_cleanup_action(db_session, user, DemoCleanupClient(), action_id=result.action_ids[0])
    db_session.commit()

    assert undo is not None
    assert "INBOX" in undo.restored_labels
    db_session.refresh(email)
    assert "INBOX" in email.labels