from datetime import UTC, datetime

from sqlalchemy import select

from app.api.deps import get_gmail_client, get_sync_queue
from app.models.feedback import EmailFeedback
from app.models.gmail import Email, GmailAccount
from app.models.sync_job import SyncJob
from app.services.gmail import GmailMessage, GmailMessageBatch, TransientGmailSyncError, create_oauth_state
from app.services.sync_jobs import create_sync_job, process_sync_job

# This test file contains tests for the Gmail integration endpoints of the FastAPI application, including OAuth flow, email synchronization, and handling of transient errors during sync jobs.
class FakeGmailClient:
    modified_messages: list[dict] = []
    def authorization_url(self, state: str) -> str:
        return f"https://accounts.google.test/oauth?state={state}"

    # Simulates exchanging an OAuth code for access and refresh tokens, returning a predefined response for testing purposes.
    def exchange_code(self, code: str):
        return {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "scope": "openid email profile https://www.googleapis.com/auth/gmail.readonly",
        }

    # Simulates refreshing an access token using a refresh token, returning a predefined access token for testing purposes.
    def refresh_access_token(self, refresh_token: str) -> str:
        assert refresh_token == "test-refresh-token"
        return "refreshed-access-token"

    # Simulates fetching the user's Gmail profile, returning a predefined email address and history ID for testing purposes.
    def fetch_profile(self, access_token: str):
        return {"emailAddress": "esha.gmail@example.com", "historyId": "history-1"}

    # Simulates fetching the latest Gmail messages, returning a predefined list of GmailMessage objects for testing purposes.
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
            # Simulates fetching Gmail messages from history, returning a predefined GmailMessageBatch object for testing purposes.
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

# Simulates fetching Gmail messages from history, returning a predefined GmailMessageBatch object for testing purposes.
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

# A subclass of FakeGmailClient that simulates a transient error when attempting to refresh the access token, used for testing error handling in sync jobs.
    def modify_message_labels(
        self,
        access_token: str,
        message_id: str,
        *,
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
    ):
        self.__class__.modified_messages.append(
            {
                "access_token": access_token,
                "message_id": message_id,
                "add_labels": add_labels or [],
                "remove_labels": remove_labels or [],
            }
        )
        return {"id": message_id, "labelIds": []}


class ManyMessagesGmailClient(FakeGmailClient):
    def fetch_latest_messages(self, access_token: str, max_results: int):
        return [
            GmailMessage(
                gmail_message_id=f"bulk-msg-{index}",
                gmail_thread_id=f"bulk-thread-{index % 50}",
                history_id=f"bulk-history-{index}",
                sender=f"Sender {index % 20} <sender{index % 20}@example.com>",
                recipients="esha@gmail.com",
                subject=f"Newsletter issue {index}",
                snippet="Weekly digest with unsubscribe link.",
                body_preview="Weekly digest with unsubscribe link.",
                labels=["INBOX", "UNREAD"] if index % 3 == 0 else ["INBOX"],
                received_at=datetime(2026, 7, 21, 10, index % 60, tzinfo=UTC),
            )
            for index in range(500)
        ]

class FailingGmailClient(FakeGmailClient):
    def refresh_access_token(self, refresh_token: str) -> str:
        raise TransientGmailSyncError("temporary timeout")


# A fake sync queue implementation that records enqueued sync job IDs for testing purposes, allowing verification of job queuing behavior in tests.
class FakeSyncQueue:
    def __init__(self) -> None:
        self.enqueued: list[int] = []

    def enqueue(self, sync_job_id: int) -> str:
        self.enqueued.append(sync_job_id)
        return "fake-celery-task"

# A fake Gmail client that simulates fetching messages for classification, returning a predefined set of messages for testing purposes.
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

# A fake Gmail client that simulates fetching messages for classification, returning a predefined set of messages for testing purposes.
def _connect_gmail(client):
    state = create_oauth_state(user_id=1)
    callback = client.post(
        "/api/v1/gmail/oauth/callback",
        json={"code": "oauth-code", "state": state},
    )
    assert callback.status_code == 200
    return callback

# Test that the Gmail OAuth callback endpoint correctly persists the first sync and behaves idempotently on subsequent calls, ensuring that duplicate syncs do not create additional records.
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
    payload = emails.json()
    assert payload["total"] == 2
    assert len(payload["items"]) == 2
    assert payload["items"][0]["subject"] == "Electricity bill"

# Test that the Gmail sync endpoint correctly queues a sync job and returns the expected response, verifying that the job is enqueued in the fake sync queue.
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

# Test that the process_sync_job function correctly processes a sync job, updates the Gmail account's history ID, and persists the fetched emails in the database.
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

# Test that the process_sync_job function correctly handles transient errors during sync jobs, marking the job as retrying and incrementing the attempt count without persisting any emails in the database.
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


def test_hybrid_search_returns_ranked_email_results(client):
    client.app.dependency_overrides[get_gmail_client] = lambda: FakeGmailClient()
    headers = _auth_headers(client)
    _connect_gmail(client)

    response = client.get("/api/v1/gmail/search?q=electricity%20bill", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "electricity bill"
    assert payload["results"]
    top = payload["results"][0]
    assert top["email"]["subject"] == "Electricity bill"
    assert top["keyword_rank"] == 1
    assert top["vector_rank"] is not None
    assert top["rrf_score"] > 0
    assert top["match_reason"] == "keyword_and_semantic"


def test_hybrid_search_is_user_scoped(client):
    client.app.dependency_overrides[get_gmail_client] = lambda: FakeGmailClient()
    headers = _auth_headers(client)
    _connect_gmail(client)

    other_signup = client.post(
        "/api/v1/auth/signup",
        json={"email": "other@example.com", "password": "supersecret", "full_name": "Other"},
    )
    assert other_signup.status_code == 201
    other_login = client.post(
        "/api/v1/auth/login",
        data={"username": "other@example.com", "password": "supersecret"},
    )
    assert other_login.status_code == 200
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    response = client.get("/api/v1/gmail/search?q=electricity", headers=other_headers)

    assert response.status_code == 200
    assert response.json()["results"] == []


def test_inbox_insights_returns_health_score_and_cleanup_suggestions(client, db_session):
    client.app.dependency_overrides[get_gmail_client] = lambda: FakeGmailClient()
    headers = _auth_headers(client)
    _connect_gmail(client)

    recruiter_email = db_session.scalar(select(Email).where(Email.gmail_message_id == "msg-1"))
    bill_email = db_session.scalar(select(Email).where(Email.gmail_message_id == "msg-2"))
    recruiter_email.priority = "high"
    recruiter_email.needs_reply = True
    recruiter_email.category = "primary"
    bill_email.category = "promotions"
    bill_email.priority = "low"
    bill_email.needs_reply = True
    bill_email.received_at = datetime.now(UTC)
    db_session.commit()

    response = client.get("/api/v1/gmail/insights", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_emails"] == 2
    assert payload["unread_count"] == 1
    assert payload["high_priority_unread_count"] == 1
    assert payload["pending_reply_count"] == 2
    assert payload["aged_follow_up_count"] == 1
    assert payload["oldest_follow_up_days"] >= payload["follow_up_age_days"]
    assert payload["cleanup_candidate_count"] == 1
    assert 0 <= payload["score"] < 100
    assert payload["formula"].startswith("100 - unread_ratio")
    suggestions = {suggestion["suggestion_type"]: suggestion for suggestion in payload["suggestions"]}
    assert {"archive_low_value", "follow_up", "read_priority", "stale_follow_up"}.issubset(suggestions)
    assert suggestions["stale_follow_up"]["email_count"] == 1
    assert suggestions["stale_follow_up"]["candidate_emails"][0]["gmail_message_id"] == "msg-1"
    assert suggestions["stale_follow_up"]["oldest_days_pending"] >= payload["follow_up_age_days"]
    assert suggestions["follow_up"]["email_count"] == 2
    assert suggestions["archive_low_value"]["candidate_emails"][0]["gmail_message_id"] == "msg-2"
    assert suggestions["archive_low_value"]["sender_breakdown"][0]["sender"] == "Bills <billing@example.com>"




def test_cleanup_preview_returns_actionable_archive_candidates(client, db_session):
    client.app.dependency_overrides[get_gmail_client] = lambda: FakeGmailClient()
    headers = _auth_headers(client)
    _connect_gmail(client)

    bill_email = db_session.scalar(select(Email).where(Email.gmail_message_id == "msg-2"))
    bill_email.category = "promotions"
    bill_email.priority = "low"
    db_session.commit()

    response = client.get("/api/v1/gmail/cleanup/preview", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_candidates"] == 1
    assert payload["estimated_time_saved_minutes"] == 0
    assert payload["items"][0]["email"]["gmail_message_id"] == "msg-2"
    assert payload["items"][0]["suggested_action"] == "archive"
    assert payload["items"][0]["reason"] == "Classified as promotions."
    assert payload["items"][0]["confidence"] == 0.9


def test_sender_insights_group_emails_by_sender(client, db_session):
    client.app.dependency_overrides[get_gmail_client] = lambda: FakeGmailClient()
    headers = _auth_headers(client)
    _connect_gmail(client)

    bill_email = db_session.scalar(select(Email).where(Email.gmail_message_id == "msg-2"))
    bill_email.category = "promotions"
    bill_email.priority = "low"
    db_session.commit()

    response = client.get("/api/v1/gmail/senders", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    bills = next(sender for sender in payload if sender["sender"] == "Bills <billing@example.com>")
    assert bills["total_emails"] == 1
    assert bills["cleanup_candidate_count"] == 1
    assert bills["suggested_action"] == "bulk_archive_review"
    assert bills["candidate_emails"][0]["gmail_message_id"] == "msg-2"


def test_cleanup_action_archives_selected_email_and_updates_local_labels(client, db_session):
    FakeGmailClient.modified_messages = []
    client.app.dependency_overrides[get_gmail_client] = lambda: FakeGmailClient()
    headers = _auth_headers(client)
    _connect_gmail(client)

    bill_email = db_session.scalar(select(Email).where(Email.gmail_message_id == "msg-2"))
    assert "INBOX" in bill_email.labels

    response = client.post(
        "/api/v1/gmail/cleanup/actions",
        headers=headers,
        json={"email_ids": [bill_email.id], "action": "archive"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "archive"
    assert payload["requested_count"] == 1
    assert payload["applied_count"] == 1
    assert payload["skipped_count"] == 0
    assert payload["emails"][0]["gmail_message_id"] == "msg-2"
    db_session.refresh(bill_email)
    assert "INBOX" not in bill_email.labels
    assert FakeGmailClient.modified_messages[-1]["remove_labels"] == ["INBOX"]


def test_feedback_endpoint_logs_correction_and_updates_email_snapshot(client, db_session):
    client.app.dependency_overrides[get_gmail_client] = lambda: FakeGmailClient()
    headers = _auth_headers(client)
    _connect_gmail(client)

    bill_email = db_session.scalar(select(Email).where(Email.gmail_message_id == "msg-2"))
    bill_email.category = "promotions"
    bill_email.priority = "low"
    bill_email.needs_reply = False
    bill_email.classification_confidence = 0.9
    bill_email.classification_model_version = "rule-engine-v1"
    db_session.commit()

    response = client.post(
        "/api/v1/gmail/feedback",
        headers=headers,
        json={
            "email_id": bill_email.id,
            "feedback_type": "not_cleanup",
            "corrected_category": "primary",
            "corrected_priority": "medium",
            "corrected_needs_reply": True,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["original_category"] == "promotions"
    assert payload["corrected_category"] == "primary"
    assert payload["model_version"] == "rule-engine-v1"
    assert db_session.scalar(select(EmailFeedback).where(EmailFeedback.email_id == bill_email.id)) is not None
    db_session.refresh(bill_email)
    assert bill_email.category == "primary"
    assert bill_email.priority == "medium"
    assert bill_email.needs_reply is True


def test_classification_evaluation_report_is_visible(client):
    client.app.dependency_overrides[get_gmail_client] = lambda: FakeGmailClient()
    headers = _auth_headers(client)

    response = client.get("/api/v1/gmail/classification/evaluation", headers=headers)

    assert response.status_code == 200
    assert "Sample size: 40" in response.json()["report_markdown"]
    assert "Macro F1" in response.json()["report_markdown"]


def test_large_scale_initial_sync_remains_idempotent_for_500_messages(client, db_session):
    client.app.dependency_overrides[get_gmail_client] = lambda: ManyMessagesGmailClient()
    _auth_headers(client)

    first_callback = _connect_gmail(client)
    second_callback = _connect_gmail(client)

    assert first_callback.json()["created_count"] == 500
    assert first_callback.json()["updated_count"] == 0
    assert second_callback.json()["created_count"] == 0
    assert second_callback.json()["updated_count"] == 500
    assert len(list(db_session.scalars(select(Email)))) == 500


def test_email_filters_and_pagination_return_scoped_page(client, db_session):
    client.app.dependency_overrides[get_gmail_client] = lambda: FakeGmailClient()
    headers = _auth_headers(client)
    _connect_gmail(client)

    bill_email = db_session.scalar(select(Email).where(Email.gmail_message_id == "msg-2"))
    bill_email.category = "promotions"
    bill_email.priority = "low"
    db_session.commit()

    response = client.get("/api/v1/gmail/emails?category=promotions&priority=low&limit=1&offset=0", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["limit"] == 1
    assert payload["offset"] == 0
    assert payload["has_more"] is False
    assert payload["items"][0]["gmail_message_id"] == "msg-2"


def test_sync_health_summarizes_job_statuses(client, db_session):
    fake_queue = FakeSyncQueue()
    client.app.dependency_overrides[get_gmail_client] = lambda: FakeGmailClient()
    client.app.dependency_overrides[get_sync_queue] = lambda: fake_queue
    headers = _auth_headers(client)
    _connect_gmail(client)

    client.post("/api/v1/gmail/sync", headers=headers)
    account = db_session.scalar(select(GmailAccount))
    retrying_job = create_sync_job(db_session, account.user, account)
    retrying_job.status = "retrying"
    retrying_job.error_type = "transient_gmail_error"
    db_session.commit()

    response = client.get("/api/v1/gmail/sync/health", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_jobs"] == 2
    assert payload["queued_jobs"] == 1
    assert payload["retrying_jobs"] == 1
    assert payload["error_counts"]["transient_gmail_error"] == 1

def test_gmail_sync_endpoint_records_per_job_max_results(client, db_session):
    fake_queue = FakeSyncQueue()
    client.app.dependency_overrides[get_gmail_client] = lambda: FakeGmailClient()
    client.app.dependency_overrides[get_sync_queue] = lambda: fake_queue
    headers = _auth_headers(client)
    _connect_gmail(client)

    response = client.post("/api/v1/gmail/sync?max_results=100", headers=headers)

    assert response.status_code == 202
    assert response.json()["max_results"] == 100
    job = db_session.get(SyncJob, response.json()["id"])
    assert job.max_results == 100


def test_gmail_client_fetch_latest_messages_follows_page_tokens(monkeypatch):
    from app.services.gmail import GmailClient

    calls = []

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_get(url, *, headers, params, timeout):
        calls.append({"url": url, "params": dict(params)})
        if url.endswith("/messages") and "pageToken" not in params:
            return FakeResponse({"messages": [{"id": "m1"}], "nextPageToken": "page-2"})
        if url.endswith("/messages") and params.get("pageToken") == "page-2":
            return FakeResponse({"messages": [{"id": "m2"}]})
        message_id = url.rsplit("/", 1)[-1]
        return FakeResponse(
            {
                "id": message_id,
                "threadId": f"thread-{message_id}",
                "historyId": f"history-{message_id}",
                "labelIds": ["INBOX"],
                "snippet": f"snippet {message_id}",
                "payload": {"headers": [{"name": "Subject", "value": f"Subject {message_id}"}]},
                "internalDate": "1785607200000",
            }
        )

    monkeypatch.setattr("app.services.gmail.httpx.get", fake_get)

    messages = GmailClient().fetch_latest_messages("access-token", max_results=2)

    assert [message.gmail_message_id for message in messages] == ["m1", "m2"]
    list_calls = [call for call in calls if call["url"].endswith("/messages")]
    assert list_calls[0]["params"]["maxResults"] == 2
    assert list_calls[1]["params"]["pageToken"] == "page-2"
