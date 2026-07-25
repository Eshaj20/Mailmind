from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlencode

import httpx
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.crypto import decrypt_value, encrypt_value
from app.models.gmail import Email, EmailThread, GmailAccount
from app.models.user import User

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
OAUTH_STATE_PURPOSE = "gmail_oauth"


@dataclass(frozen=True)
class GmailMessage:
    gmail_message_id: str
    gmail_thread_id: str
    history_id: str | None
    sender: str | None
    recipients: str | None
    subject: str | None
    snippet: str | None
    body_preview: str | None
    labels: list[str]
    received_at: datetime | None


@dataclass(frozen=True)
class GmailSyncStats:
    synced_count: int
    created_count: int
    updated_count: int


def create_oauth_state(user_id: int) -> str:
    payload = {"sub": str(user_id), "purpose": OAUTH_STATE_PURPOSE}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def parse_oauth_state(state: str) -> int:
    try:
        payload = jwt.decode(state, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid OAuth state") from exc

    if payload.get("purpose") != OAUTH_STATE_PURPOSE or not payload.get("sub"):
        raise ValueError("Invalid OAuth state")
    return int(payload["sub"])


class GmailClient:
    def __init__(self, config: Settings = settings) -> None:
        self.config = config

    def authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.config.google_client_id,
            "redirect_uri": self.config.google_redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.config.gmail_scope_list),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> dict[str, Any]:
        response = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": self.config.google_client_id,
                "client_secret": self.config.google_client_secret,
                "redirect_uri": self.config.google_redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def refresh_access_token(self, refresh_token: str) -> str:
        response = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": self.config.google_client_id,
                "client_secret": self.config.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=15,
        )
        response.raise_for_status()
        return str(response.json()["access_token"])

    def fetch_profile(self, access_token: str) -> dict[str, Any]:
        response = httpx.get(
            f"{GMAIL_API_BASE}/profile",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def fetch_latest_messages(self, access_token: str, max_results: int) -> list[GmailMessage]:
        list_response = httpx.get(
            f"{GMAIL_API_BASE}/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"maxResults": max_results, "q": "newer_than:30d"},
            timeout=15,
        )
        list_response.raise_for_status()
        message_refs = list_response.json().get("messages", [])

        messages: list[GmailMessage] = []
        for item in message_refs:
            message_response = httpx.get(
                f"{GMAIL_API_BASE}/messages/{item['id']}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"format": "metadata", "metadataHeaders": ["From", "To", "Subject", "Date"]},
                timeout=15,
            )
            message_response.raise_for_status()
            messages.append(parse_gmail_message(message_response.json()))
        return messages


def parse_gmail_message(payload: dict[str, Any]) -> GmailMessage:
    headers = {
        header.get("name", "").lower(): header.get("value")
        for header in payload.get("payload", {}).get("headers", [])
    }
    labels = payload.get("labelIds", []) or []
    received_at = _parse_received_at(headers.get("date"), payload.get("internalDate"))
    return GmailMessage(
        gmail_message_id=payload["id"],
        gmail_thread_id=payload.get("threadId", payload["id"]),
        history_id=payload.get("historyId"),
        sender=headers.get("from"),
        recipients=headers.get("to"),
        subject=headers.get("subject"),
        snippet=payload.get("snippet"),
        body_preview=payload.get("snippet"),
        labels=labels,
        received_at=received_at,
    )


def _parse_received_at(header_date: str | None, internal_date: str | None) -> datetime | None:
    if header_date:
        try:
            parsed = parsedate_to_datetime(header_date)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed
        except (TypeError, ValueError):
            pass
    if internal_date:
        try:
            return datetime.fromtimestamp(int(internal_date) / 1000, tz=UTC)
        except (TypeError, ValueError):
            return None
    return None


def upsert_gmail_account(
    db: Session,
    user: User,
    google_email: str,
    refresh_token: str | None,
    scopes: list[str],
    history_id: str | None,
) -> GmailAccount:
    account = db.scalar(
        select(GmailAccount).where(
            GmailAccount.user_id == user.id,
            GmailAccount.google_email == google_email,
        )
    )
    if account is None:
        account = GmailAccount(user_id=user.id, google_email=google_email)
        db.add(account)

    if refresh_token:
        account.refresh_token_ciphertext = encrypt_value(refresh_token)
    account.scopes = scopes
    account.history_id = history_id or account.history_id
    account.sync_status = "connected"
    return account


def sync_latest_messages(
    db: Session,
    user: User,
    account: GmailAccount,
    messages: list[GmailMessage],
) -> GmailSyncStats:
    created_count = 0
    updated_count = 0
    latest_history_id = account.history_id

    for message in messages:
        thread = db.scalar(
            select(EmailThread).where(
                EmailThread.gmail_account_id == account.id,
                EmailThread.gmail_thread_id == message.gmail_thread_id,
            )
        )
        if thread is None:
            thread = EmailThread(
                user_id=user.id,
                gmail_account_id=account.id,
                gmail_thread_id=message.gmail_thread_id,
            )
            db.add(thread)

        thread.subject = message.subject
        thread.snippet = message.snippet
        if message.received_at and (
            thread.last_message_at is None or _as_utc(message.received_at) > _as_utc(thread.last_message_at)
        ):
            thread.last_message_at = message.received_at

        db.flush()

        email = db.scalar(
            select(Email).where(
                Email.gmail_account_id == account.id,
                Email.gmail_message_id == message.gmail_message_id,
            )
        )
        if email is None:
            email = Email(
                user_id=user.id,
                gmail_account_id=account.id,
                thread_id=thread.id,
                gmail_message_id=message.gmail_message_id,
            )
            db.add(email)
            created_count += 1
        else:
            updated_count += 1

        email.thread_id = thread.id
        email.sender = message.sender
        email.recipients = message.recipients
        email.subject = message.subject
        email.snippet = message.snippet
        email.body_preview = message.body_preview
        email.labels = message.labels
        email.is_read = "UNREAD" not in message.labels
        email.received_at = message.received_at
        latest_history_id = message.history_id or latest_history_id

    account.history_id = latest_history_id
    account.last_synced_at = datetime.now(UTC)
    account.sync_status = "synced"
    db.flush()
    return GmailSyncStats(
        synced_count=len(messages),
        created_count=created_count,
        updated_count=updated_count,
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def sync_account_with_refresh_token(
    db: Session,
    user: User,
    account: GmailAccount,
    client: GmailClient,
    max_results: int,
) -> GmailSyncStats:
    refresh_token = decrypt_value(account.refresh_token_ciphertext)
    access_token = client.refresh_access_token(refresh_token)
    messages = client.fetch_latest_messages(access_token, max_results=max_results)
    return sync_latest_messages(db, user, account, messages)



