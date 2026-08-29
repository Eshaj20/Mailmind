from datetime import UTC, datetime

from app.models.gmail import Email, EmailThread, GmailAccount
from app.models.user import User
from scripts.benchmark_search import evaluate_queries


def _seed_email(db_session, user: User, account: GmailAccount, *, message_id: str, thread_id: int, subject: str, body: str) -> Email:
    thread = EmailThread(
        user_id=user.id,
        gmail_account_id=account.id,
        gmail_thread_id=f"thread-{thread_id}",
        subject=subject,
        snippet=body,
        last_message_at=datetime(2026, 8, 25, 10, thread_id, tzinfo=UTC),
    )
    db_session.add(thread)
    db_session.flush()
    email = Email(
        user_id=user.id,
        gmail_account_id=account.id,
        thread_id=thread.id,
        gmail_message_id=message_id,
        sender="Sender <sender@example.com>",
        recipients="esha@example.com",
        subject=subject,
        snippet=body,
        body_preview=body,
        labels=["INBOX"],
        is_read=False,
        received_at=datetime(2026, 8, 25, 10, thread_id, tzinfo=UTC),
    )
    db_session.add(email)
    db_session.flush()
    return email


def test_search_benchmark_compares_keyword_vector_and_hybrid_modes(db_session):
    user = User(email="search@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.flush()
    account = GmailAccount(
        user_id=user.id,
        google_email="search.gmail@example.com",
        refresh_token_ciphertext="encrypted-token",
        scopes=["gmail.readonly"],
    )
    db_session.add(account)
    db_session.flush()

    bill_email = _seed_email(
        db_session,
        user,
        account,
        message_id="bill-1",
        thread_id=1,
        subject="Electricity bill for August",
        body="Your electricity bill and payment receipt are ready.",
    )
    interview_email = _seed_email(
        db_session,
        user,
        account,
        message_id="interview-1",
        thread_id=2,
        subject="Backend interview schedule",
        body="Can we schedule your founder call for the backend role?",
    )
    db_session.commit()

    report = evaluate_queries(
        [
            {"query": "electricity bill", "expected_email_id": str(bill_email.id)},
            {"query": "backend interview", "expected_email_id": str(interview_email.id)},
        ],
        user,
        db_session,
    )

    assert report["query_count"] == 2
    assert set(report["modes"]) == {"keyword", "vector", "hybrid"}
    assert report["modes"]["keyword"]["hit_at_3"] == 1.0
    assert report["modes"]["vector"]["hit_at_3"] == 1.0
    assert report["modes"]["hybrid"]["hit_at_3"] == 1.0
    assert report["best_mode"] in {"keyword", "vector", "hybrid"}
    assert report["details"][0]["hybrid"]["top_email_id"] == bill_email.id
