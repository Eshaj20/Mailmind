from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_value
from app.models.cleanup_action import CleanupActionLog
from app.models.gmail import Email, GmailAccount
from app.models.user import User
from app.services.gmail import GmailClient

CleanupAction = Literal["archive", "mark_read"]


@dataclass(frozen=True)
class CleanupActionResult:
    action: CleanupAction
    requested_count: int
    applied_count: int
    skipped_count: int
    emails: list[Email]
    action_ids: list[int]


@dataclass(frozen=True)
class CleanupUndoResult:
    action_id: int
    action: str
    email: Email
    restored_labels: list[str]
    restored_is_read: bool


def apply_cleanup_action(
    db: Session,
    user: User,
    client: GmailClient,
    *,
    email_ids: list[int],
    action: CleanupAction,
) -> CleanupActionResult:
    """Apply a user-confirmed Gmail cleanup action and record undo state.

    The function deliberately works from explicit email IDs instead of an entire
    suggestion bucket. That keeps the AI assistant review-first: MailMind can
    recommend, but the user chooses exactly what gets archived or marked read.
    """
    unique_ids = list(dict.fromkeys(email_ids))
    if not unique_ids:
        return CleanupActionResult(
            action=action,
            requested_count=0,
            applied_count=0,
            skipped_count=0,
            emails=[],
            action_ids=[],
        )

    emails = list(
        db.scalars(
            select(Email)
            .where(Email.user_id == user.id, Email.id.in_(unique_ids))
            .order_by(Email.id)
        )
    )
    requested_by_id = set(unique_ids)
    found_by_id = {email.id for email in emails}
    skipped_count = len(requested_by_id - found_by_id)

    accounts = {
        account.id: account
        for account in db.scalars(select(GmailAccount).where(GmailAccount.user_id == user.id))
    }
    access_tokens: dict[int, str] = {}
    applied: list[Email] = []
    action_ids: list[int] = []

    for email in emails:
        account = accounts.get(email.gmail_account_id)
        if account is None:
            skipped_count += 1
            continue

        remove_labels = _labels_to_remove(action)
        previous_labels = list(email.labels or [])
        previous_is_read = email.is_read

        if not _is_demo_account(account):
            if account.id not in access_tokens:
                access_tokens[account.id] = client.refresh_access_token(decrypt_value(account.refresh_token_ciphertext))
            client.modify_message_labels(
                access_tokens[account.id],
                email.gmail_message_id,
                remove_labels=remove_labels,
            )
        log_entry = CleanupActionLog(
            user_id=user.id,
            email_id=email.id,
            gmail_account_id=email.gmail_account_id,
            action=action,
            gmail_message_id=email.gmail_message_id,
            previous_labels=previous_labels,
            previous_is_read=previous_is_read,
        )
        db.add(log_entry)
        db.flush()
        action_ids.append(log_entry.id)
        _mirror_action_locally(email, action=action, remove_labels=remove_labels)
        applied.append(email)

    db.flush()
    return CleanupActionResult(
        action=action,
        requested_count=len(unique_ids),
        applied_count=len(applied),
        skipped_count=skipped_count,
        emails=applied,
        action_ids=action_ids,
    )


def undo_cleanup_action(
    db: Session,
    user: User,
    client: GmailClient,
    *,
    action_id: int,
) -> CleanupUndoResult | None:
    """Undo one previously applied cleanup action for the current user."""
    log_entry = db.scalar(
        select(CleanupActionLog).where(
            CleanupActionLog.id == action_id,
            CleanupActionLog.user_id == user.id,
        )
    )
    if log_entry is None or log_entry.undone_at is not None:
        return None

    email = db.scalar(select(Email).where(Email.id == log_entry.email_id, Email.user_id == user.id))
    account = db.scalar(select(GmailAccount).where(GmailAccount.id == log_entry.gmail_account_id, GmailAccount.user_id == user.id))
    if email is None or account is None:
        return None

    current_labels = set(email.labels or [])
    previous_labels = list(log_entry.previous_labels or [])
    labels_to_restore = [label for label in previous_labels if label not in current_labels]
    if labels_to_restore and not _is_demo_account(account):
        access_token = client.refresh_access_token(decrypt_value(account.refresh_token_ciphertext))
        client.modify_message_labels(
            access_token,
            log_entry.gmail_message_id,
            add_labels=labels_to_restore,
        )

    email.labels = previous_labels
    email.is_read = log_entry.previous_is_read
    log_entry.undone_at = datetime.now(UTC)
    db.flush()
    return CleanupUndoResult(
        action_id=log_entry.id,
        action=log_entry.action,
        email=email,
        restored_labels=previous_labels,
        restored_is_read=email.is_read,
    )


def _labels_to_remove(action: CleanupAction) -> list[str]:
    if action == "archive":
        return ["INBOX"]
    if action == "mark_read":
        return ["UNREAD"]
    raise ValueError(f"Unsupported cleanup action: {action}")


def _mirror_action_locally(email: Email, *, action: CleanupAction, remove_labels: list[str]) -> None:
    labels = [label for label in (email.labels or []) if label not in set(remove_labels)]
    email.labels = labels
    if action == "mark_read" or "UNREAD" in remove_labels:
        email.is_read = True

def _is_demo_account(account: GmailAccount) -> bool:
    """Demo inboxes use synthetic data, so cleanup actions stay local-only."""
    scopes = set(account.scopes or [])
    return "demo" in scopes or account.google_email.endswith("@mailmind.dev")