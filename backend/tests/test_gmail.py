from datetime import UTC, datetime

from app.api.deps import get_gmail_client
from app.services.gmail import GmailMessage, create_oauth_state


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


def test_gmail_oauth_callback_persists_first_sync_idempotently(client):
    client.app.dependency_overrides[get_gmail_client] = lambda: FakeGmailClient()
    headers = _auth_headers(client)

    authorize = client.get("/api/v1/gmail/oauth/authorize", headers=headers)
    assert authorize.status_code == 200
    assert "accounts.google.test" in authorize.json()["authorization_url"]

    state = create_oauth_state(user_id=1)
    first_callback = client.post(
        "/api/v1/gmail/oauth/callback",
        json={"code": "oauth-code", "state": state},
    )
    assert first_callback.status_code == 200
    assert first_callback.json()["created_count"] == 2
    assert first_callback.json()["updated_count"] == 0
    assert first_callback.json()["account"]["google_email"] == "esha.gmail@example.com"

    second_callback = client.post(
        "/api/v1/gmail/oauth/callback",
        json={"code": "oauth-code", "state": state},
    )
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
