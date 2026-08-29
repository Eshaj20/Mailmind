from datetime import UTC, datetime

from sqlalchemy import select

# Import application modules after setting up the environment
from app.api.deps import get_db, get_gmail_client, get_llm_client
from app.models.ai_usage import AIUsageLog
from app.api.deps import get_gmail_client, get_llm_client
from app.models.gmail import Email, EmailThread
from app.services.classification import (
    LLMClient,
    apply_rule_engine,
    classify_fields,
    classify_unclassified_emails,
)
from app.services.evaluation import evaluate_classifier

# --- Fixtures and helpers ------------------------------------------------------
class FakeGmailClientForClassification:
    """Minimal Gmail fake reused from test_gmail.py's pattern, scoped to this file
    so classification tests don't depend on emails already existing in the DB."""

#   is_configured = True
    def authorization_url(self, state: str) -> str:
        return f"https://accounts.google.test/oauth?state={state}"

    # Mock the exchange_code and fetch_profile methods to return test data
    def exchange_code(self, code: str):
        return {"access_token": "test-access-token", "refresh_token": "test-refresh-token", "scope": "openid"}

    # Mock the fetch_profile and fetch_latest_messages methods to return test data
    def fetch_profile(self, access_token: str):
        return {"emailAddress": "esha.gmail@example.com", "historyId": "history-1"}

    # Mock the fetch_latest_messages method to return a list of test messages
    def fetch_latest_messages(self, access_token: str, max_results: int):
        from app.services.gmail import GmailMessage

        # Return a list of GmailMessage objects with test data
        return [
            GmailMessage(
                gmail_message_id="msg-promo",
                gmail_thread_id="thread-promo",
                history_id="history-2",
                sender="Deals <deals@outletstore.com>",
                recipients="esha@gmail.com",
                subject="50% off everything this weekend",
                snippet="Huge sale, 50% off everything, unsubscribe anytime.",
                body_preview="Huge sale, 50% off everything, unsubscribe anytime.",
                labels=["INBOX"],
                received_at=datetime(2026, 8, 1, 10, 0, tzinfo=UTC),
            ),

            # Add a second message to the list for testing purposes
            GmailMessage(
                gmail_message_id="msg-interview",
                gmail_thread_id="thread-interview",
                history_id="history-3",
                sender="Recruiter <recruiter@example.com>",
                recipients="esha@gmail.com",
                subject="Interview availability - action required",
                snippet="Can we schedule your interview? Please respond by Friday.",
                body_preview="Can we schedule your interview? Please respond by Friday.",
                labels=["INBOX", "UNREAD"],
                received_at=datetime(2026, 8, 1, 11, 0, tzinfo=UTC),
            ),
        ]

# --- Classification service unit tests ----------------------------------------
class FakeLLMClient:
    """Deterministic stand-in for the OpenAI-backed LLMClient, used to prove the
    endpoint wires through a configured LLM without making network calls."""

    is_configured = True
    model = "fake-model"

    # Mock the classify and summarize methods to return test data
    def classify(self, subject, sender, snippet, body_preview):
        return {
            "category": "primary",
            "priority": "high",
            "needs_reply": True,
            "confidence": 0.91,
            "rationale": "fake llm says so",
        }

        # Mock the summarize method to return a test summary
    def summarize(self, subject, messages):
        return "Fake LLM summary of the thread."

# --- Helper functions for tests ------------------------------------------------
# Helper function to perform signup and login, returning the authorization headers
def _auth_headers(client):
    signup = client.post(
        "/api/v1/auth/signup",
        json={"email": "esha@example.com", "password": "supersecret", "full_name": "Esha"},
    )
    assert signup.status_code == 201

    # Perform login to obtain the access token
    login = client.post(
        "/api/v1/auth/login",
        data={"username": "esha@example.com", "password": "supersecret"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}

# Helper function to simulate connecting a Gmail account for the test user
def _connect_gmail(client):
    from app.services.gmail import create_oauth_state

    state = create_oauth_state(user_id=1)
    callback = client.post("/api/v1/gmail/oauth/callback", json={"code": "oauth-code", "state": state})
    assert callback.status_code == 200
    return callback


# --- Rule engine unit tests -------------------------------------------------

# Test cases for the rule engine classification logic, ensuring that it correctly classifies emails based on predefined rules.
def test_rule_engine_classifies_obvious_promotion_confidently():
    result = apply_rule_engine(
        subject="50% off everything this weekend",
        sender="deals@outletstore.com",
        snippet="Huge sale, 50% off everything, unsubscribe anytime.",
        body_preview=None,
    )
    assert result is not None
    assert result.category == "promotions"
    assert result.needs_reply is False
    assert result.stage == "rule"
    assert result.confidence >= 0.75

# Test that the rule engine flags an important email as primary with high priority and needing a reply.
def test_rule_engine_flags_important_email_as_primary_high_priority():
    result = apply_rule_engine(
        subject="Interview availability - action required",
        sender="recruiter@example.com",
        snippet="Can we schedule your interview? Please respond by Friday.",
        body_preview=None,
    )
    assert result is not None
    assert result.category == "primary"
    assert result.priority == "high"
    assert result.needs_reply is True

# Test that the rule engine returns None for an ambiguous email that doesn't match any specific rules.
def test_rule_engine_returns_none_for_ambiguous_email():
    result = apply_rule_engine(
        subject="Quick note",
        sender="friend@example.com",
        snippet="Saw this and thought of you.",
        body_preview=None,
    )
    assert result is None

# --- Classification service unit tests ----------------------------------------

# Test that the classify_fields function falls back to lightweight classification when no LLM is provided.
def test_classify_fields_falls_back_to_lightweight_without_llm():
    result = classify_fields(
        subject="Quick note",
        sender="friend@example.com",
        snippet="Saw this and thought of you.",
        body_preview=None,
        llm_client=LLMClient(api_key=""),
    )
    assert result.stage == "lightweight"
    assert result.category in ("primary", "promotions", "social", "updates", "spam")
    assert 0.0 <= result.confidence <= 1.0

# Test that the classify_fields function uses the LLM for classification when it is provided and the rule engine is ambiguous.
def test_classify_fields_uses_llm_when_configured_and_rule_is_ambiguous():
    result = classify_fields(
        subject="Quick note",
        sender="friend@example.com",
        snippet="Saw this and thought of you.",
        body_preview=None,
        llm_client=FakeLLMClient(),
    )
    assert result.stage == "llm"
    assert result.category == "primary"
    assert result.model_version == "openai:fake-model"


# --- Evaluation harness ------------------------------------------------------

# Test that the evaluate_classifier function correctly evaluates the classifier's performance against labeled rows.
def test_evaluate_classifier_scores_against_labeled_rows():
    rows = [
        {
            "sender": "deals@outletstore.com",
            "subject": "50% off everything",
            "snippet": "Huge sale, unsubscribe anytime.",
            "body_preview": "",
            "label_category": "promotions",
            "label_priority": "low",
            "label_needs_reply": "false",
        },
        {
            "sender": "recruiter@example.com",
            "subject": "Interview availability - action required",
            "snippet": "Can we schedule your interview? Please respond by Friday.",
            "body_preview": "",
            "label_category": "primary",
            "label_priority": "high",
            "label_needs_reply": "true",
        },
    ]
    report = evaluate_classifier(rows, llm_client=LLMClient(api_key=""))
    assert report["sample_count"] == 2
    assert report["category"]["accuracy"] == 1.0
    assert "rule" in report["stage_counts"]


# --- API endpoint tests ------------------------------------------------------

# Test that the /classify endpoint correctly classifies emails, stores metadata, and summarizes threads.
def test_classify_endpoint_stores_metadata_and_summarizes_threads(client, db_session):
    client.app.dependency_overrides[get_gmail_client] = lambda: FakeGmailClientForClassification()
    headers = _auth_headers(client)
    _connect_gmail(client)

    response = client.post("/api/v1/gmail/classify", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["classified_count"] == 2
    assert body["by_category"]["promotions"] == 1
    assert body["by_category"]["primary"] == 1
    assert body["needs_reply_count"] == 1

    # Verify that the emails and threads are stored in the database with the expected classification metadata
    emails = client.get("/api/v1/gmail/emails", headers=headers).json()
    by_id = {e["gmail_message_id"]: e for e in emails}
    assert by_id["msg-promo"]["category"] == "promotions"
    assert by_id["msg-promo"]["needs_reply"] is False
    assert by_id["msg-interview"]["category"] == "primary"
    assert by_id["msg-interview"]["needs_reply"] is True
    assert by_id["msg-interview"]["classification_model_version"] == "rule-engine-v1"

# Verify that the threads are stored in the database with the expected summary metadata
    threads = client.get("/api/v1/gmail/threads", headers=headers).json()
    assert len(threads) == 2
    assert all(t["summary"] for t in threads)

# Verify that the summary endpoint returns the correct counts of classified and unclassified emails
    summary = client.get("/api/v1/gmail/classification/summary", headers=headers).json()
    assert summary["total_classified"] == 2
    assert summary["total_unclassified"] == 0

    # Re-running classify should be a no-op since both emails are already classified.
    # Verify that the second classify request returns a classified_count of 0.
    second_response = client.post("/api/v1/gmail/classify", headers=headers)
    assert second_response.json()["classified_count"] == 0

# Test that the /classify endpoint uses the injected LLM client for classification when provided, and that it correctly stores the classification results in the database.
def test_classify_endpoint_uses_injected_llm_client(client, db_session):
    client.app.dependency_overrides[get_gmail_client] = lambda: FakeGmailClientForClassification()
    client.app.dependency_overrides[get_llm_client] = lambda: FakeLLMClient()
    headers = _auth_headers(client)
    _connect_gmail(client)

# Verify that the /classify endpoint correctly classifies emails using the injected LLM client and stores the results in the database.
    client.post("/api/v1/gmail/classify", headers=headers)

    email = db_session.scalar(select(Email).where(Email.gmail_message_id == "msg-promo"))
    assert email.classification_model_version == "rule-engine-v1"  # confident rule match wins, LLM unused

# Verify that the thread summary is stored in the database with the expected summary and model version.
    thread = db_session.scalar(select(EmailThread).where(EmailThread.gmail_thread_id == "thread-promo"))
    assert thread.summary == "Fake LLM summary of the thread."
    assert thread.summary_model_version == "openai:fake-model"


# Test that the /summarize endpoint correctly summarizes a specific email thread and returns the expected summary and model version.
def test_thread_summarize_endpoint(client, db_session):
    client.app.dependency_overrides[get_gmail_client] = lambda: FakeGmailClientForClassification()
    headers = _auth_headers(client)
    _connect_gmail(client)

    thread = db_session.scalar(select(EmailThread).where(EmailThread.gmail_thread_id == "thread-promo"))

    # Verify that the /summarize endpoint correctly summarizes the specified email thread and returns the expected summary and model version.
    response = client.post(f"/api/v1/gmail/threads/{thread.id}/summarize", headers=headers)
    assert response.status_code == 200
    assert response.json()["summary"]
    assert response.json()["summary_model_version"] == "lightweight-v1"

# Test that the classify_unclassified_emails service function is idempotent, meaning that running it multiple times does not change the classification results for already classified emails.
def test_classify_unclassified_emails_service_is_idempotent(db_session):
    from app.models.gmail import Email, EmailThread, GmailAccount
    from app.models.user import User

    user = User(email="svc@example.com", hashed_password="x")
    db_session.add(user)
    db_session.flush()
    account = GmailAccount(user_id=user.id, google_email="svc@gmail.com", refresh_token_ciphertext="enc")
    db_session.add(account)
    db_session.flush()
    thread = EmailThread(user_id=user.id, gmail_account_id=account.id, gmail_thread_id="t-1", subject="Sale")
    db_session.add(thread)
    db_session.flush()
    email = Email(
        user_id=user.id,
        gmail_account_id=account.id,
        thread_id=thread.id,
        gmail_message_id="m-1",
        sender="deals@outletstore.com",
        subject="50% off everything",
        snippet="Huge sale, unsubscribe anytime.",
    )
    db_session.add(email)
    db_session.commit()

    # Verify that the classify_unclassified_emails function correctly classifies unclassified emails and returns the expected statistics.
    stats = classify_unclassified_emails(db_session, user, llm_client=LLMClient(api_key=""))
    assert stats.classified_count == 1
    assert stats.by_category.get("promotions") == 1

    # Verify that running classify_unclassified_emails again does not change the classification results for already classified emails, demonstrating idempotency.
    stats_again = classify_unclassified_emails(db_session, user, llm_client=LLMClient(api_key=""))
    assert stats_again.classified_count == 0


def test_classification_records_ai_usage_summary(client, db_session):
    client.app.dependency_overrides[get_gmail_client] = lambda: FakeGmailClientForClassification()
    headers = _auth_headers(client)
    _connect_gmail(client)

    response = client.post("/api/v1/gmail/classify", headers=headers)
    assert response.status_code == 200

    usage_logs = list(db_session.scalars(select(AIUsageLog)))
    assert len(usage_logs) == 4  # 2 classifications + 2 thread summaries
    assert {log.feature for log in usage_logs} == {"classification", "thread_summary"}
    assert all(log.total_tokens > 0 for log in usage_logs)

    summary = client.get("/api/v1/gmail/ai/usage", headers=headers)
    assert summary.status_code == 200
    payload = summary.json()
    assert payload["total_calls"] == 4
    assert payload["total_tokens"] == sum(log.total_tokens for log in usage_logs)
    assert payload["by_feature"]["classification"] == 2
    assert payload["by_feature"]["thread_summary"] == 2
