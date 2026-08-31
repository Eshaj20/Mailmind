from sqlalchemy import select

from app.models.gmail import Email
from app.models.user import User
from scripts.benchmark_large_inbox import render_markdown, run_large_inbox_benchmark
from scripts.seed_large_inbox import LARGE_EMAIL, seed_large_inbox


def test_large_inbox_seed_creates_classified_searchable_emails(db_session):
    result = seed_large_inbox(db_session, count=40, reset=True, batch_size=10)
    user = db_session.scalar(select(User).where(User.email == LARGE_EMAIL))
    emails = list(db_session.scalars(select(Email).where(Email.user_id == user.id)))

    assert result["total_count"] == 40
    assert result["classified_count"] == 40
    assert len(emails) == 40
    assert all(email.classified_at is not None for email in emails)
    assert all(email.search_embedding for email in emails)
    assert any((email.spam_score or 0.0) >= 0.7 for email in emails)


def test_large_inbox_benchmark_reports_cleanup_and_search_metrics(db_session):
    report = run_large_inbox_benchmark(db_session, seed_count=50, reset=True, batch_size=10)
    markdown = render_markdown(report)

    assert report["counts"]["total_emails"] == 50
    assert report["counts"]["classified_emails"] == 50
    assert report["cleanup_preview"]["total_candidates"] > 0
    assert report["search"]["avg_latency_ms"] >= 0
    assert "Large Inbox Benchmark" in markdown
    assert "Cleanup candidates" in markdown


def test_large_inbox_seed_is_idempotent_without_reset(db_session):
    first = seed_large_inbox(db_session, count=25, reset=True, batch_size=10)
    second = seed_large_inbox(db_session, count=25, reset=False, batch_size=10)

    assert first["total_count"] == 25
    assert second["total_count"] == 25
    assert second["created_count"] == 0