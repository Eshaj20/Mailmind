from sqlalchemy import select

from app.models.classification import EmailClassification
from app.models.gmail import Email, GmailAccount
from app.models.sync_job import SyncJob
from app.models.user import User
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
    assert account.google_email == "demo.inbox@mailmind.local"
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