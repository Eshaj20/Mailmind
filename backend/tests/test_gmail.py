from datetime import UTC, datetime

from sqlalchemy import select

from app.api.deps import get_gmail_client, get_sync_queue
from app.models.gmail import Email, GmailAccount
from app.models.sync_job import SyncJob
from app.services.gmail import GmailMessage, GmailMessageBatch, TransientGmailSyncError, create_oauth_state
from app.services.sync_jobs import create_sync_job, process_sync_job


class FakeGmailClient:
    def authorization_url(self, state: str) -> str:
        return f"https://accounts.google.test/oauth?state={state}"

    def exchange_code(self, code: str):
        return {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "scope": "openid email profile https://www.googleapis.com/auth/gmail.readonly",
        }

    def refresh_access_token(self, refresh_token: str) -> str:
        assert refresh_token == "test-refresh-token"
        return "refreshed-access-token"

    def fetch_profile(self, access_token: str):
        return {"emailAddress": "esha.gmail@example.com", "historyId": "history-1"}

    def fetch_latest_messages(self, access_token: str, max_results: int):
        assert max_results > 0
        return [
            GmailMessage(
                gmail_message_id="msg-1",
                gmail_thread_id="thread-1",
                history_id="history-2",
                sender="Recruiter <recruiter@example.com>",
                recipients="esha@gmail.com",
                subject="Interview schedule",
                snippet="Can we schedule your interview?",
                body_preview="Can we schedule your interview?",
                labels=["INBOX", "UNREAD"],
                received_at=datetime(2026, 7, 21, 10, 0, tzinfo=UTC),
            ),
            GmailMessage(
                gmail_message_id="msg-2",
                gmail_thread_id="thread-2",
                history_id="history-3",
                sender="Bills <billing@example.com>",
                recipients="esha@gmail.com",
                subject="Electricity bill",
                snippet="Your electricity bill is ready.",
                body_preview="Your electricity bill is ready.",
                labels=["INBOX"],
                received_at=datetime(2026, 7, 21, 11, 0, tzinfo=UTC),
            ),
        ]

    def fetch_history_messages(self, access_token: str, start_history_id: str, max_results: int):
        assert start_history_id == "history-3"
        return GmailMessageBatch(
            history_id="history-4",
            messages=[
                GmailMessage(
                    gmail_message_id="msg-3",
                    gmail_thread_id="thread-3",
                    history_id="history-4",
                    sender="Founder <founder@example.com>",
                    recipients="esha@gmail.com",
                    subject="Follow up",
                    snippet="Following up on the interview loop.",
                    body_preview="Following up on the interview loop.",
                    labels=["INBOX", "UNREAD"],
                    received_at=datetime(2026, 7, 22, 9, 0, tzinfo=UTC),
                )
            ],
        )


class FailingGmailClient(FakeGmailClient):
    def refresh_access_token(self, refresh_token: str) -> str:
        raise TransientGmailSyncError("temporary timeout")


class FakeSyncQueue:
    def __init__(self) -> None:
        self.enqueued: list[int] = []

    def enqueue(self, sync_job_id: int) -> str:
        self.enqueued.append(sync_job_id)
        return "fake-celery-task"


def _auth_headers(client):
    signup = client.post(
        "/api/v1/auth/signup",
        json={"email": "esha@example.com", "password": "supersecret", "full_name": "Esha"},
    )
    assert signup.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        data={"username": "esha@example.com", "password": "supersecret"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _connect_gmail(client):
    state = create_oauth_state(user_id=1)
    callback = client.post(
        "/api/v1/gmail/oauth/callback",
        json={"code": "oauth-code", "state": state},
    )
    assert callback.status_code == 200
    return callback


def test_gmail_oauth_callback_persists_first_sync_idempotently(client):
    client.app.dependency_overrides[get_gmail_client] = lambda: FakeGmailClient()
    headers = _auth_headers(client)

    authorize = client.get("/api/v1/gmail/oauth/authorize", headers=headers)
    assert authorize.status_code == 200
    assert "accounts.google.test" in authorize.json()["authorization_url"]

    first_callback = _connect_gmail(client)
    assert first_callback.json()["created_count"] == 2
    assert first_callback.json()["updated_count"] == 0
    assert first_callback.json()["account"]["google_email"] == "esha.gmail@example.com"

    second_callback = _connect_gmail(client)
    assert second_callback.status_code == 200
    assert second_callback.json()["created_count"] == 0
    assert second_callback.json()["updated_count"] == 2

    accounts = client.get("/api/v1/gmail/accounts", headers=headers)
    assert accounts.status_code == 200
    assert len(accounts.json()) == 1

    emails = client.get("/api/v1/gmail/emails", headers=headers)
    assert emails.status_code == 200
    assert len(emails.json()) == 2
    assert emails.json()[0]["subject"] == "Electricity bill"


def test_gmail_sync_endpoint_queues_job(client):
    fake_queue = FakeSyncQueue()
    client.app.dependency_overrides[get_gmail_client] = lambda: FakeGmailClient()
    client.app.dependency_overrides[get_sync_queue] = lambda: fake_queue
    headers = _auth_headers(client)
    _connect_gmail(client)

    response = client.post("/api/v1/gmail/sync", headers=headers)
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert response.json()["celery_task_id"] == "fake-celery-task"
    assert fake_queue.enqueued == [response.json()["id"]]

    jobs = client.get("/api/v1/gmail/sync/jobs", headers=headers)
    assert jobs.status_code == 200
    assert len(jobs.json()) == 1


def test_process_sync_job_uses_history_id_incrementally(client, db_session):
    client.app.dependency_overrides[get_gmail_client] = lambda: FakeGmailClient()
    headers = _auth_headers(client)
    _connect_gmail(client)
    account = db_session.scalar(select(GmailAccount))
    user = account.user
    job = create_sync_job(db_session, user, account)
    db_session.commit()

    processed = process_sync_job(db_session, job.id, client=FakeGmailClient())
    db_session.refresh(account)

    assert processed.status == "succeeded"
    assert processed.created_count == 1
    assert processed.updated_count == 0
    assert account.history_id == "history-4"
    assert db_session.scalar(select(Email).where(Email.gmail_message_id == "msg-3")) is not None


def test_process_sync_job_marks_transient_failure_retrying(client, db_session):
    client.app.dependency_overrides[get_gmail_client] = lambda: FakeGmailClient()
    _auth_headers(client)
    _connect_gmail(client)
    account = db_session.scalar(select(GmailAccount))
    job = create_sync_job(db_session, account.user, account)
    db_session.commit()

    processed = process_sync_job(db_session, job.id, client=FailingGmailClient())

    assert processed.status == "retrying"
    assert processed.attempt_count == 1
    assert processed.error_type == "transient_gmail_error"
    assert db_session.scalar(select(SyncJob).where(SyncJob.id == job.id)).status == "retrying"
