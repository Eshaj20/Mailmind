from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_value
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


def apply_cleanup_action(
    db: Session,
    user: User,
    client: GmailClient,
    *,
    email_ids: list[int],
    action: CleanupAction,
) -> CleanupActionResult:
    """Apply a user-confirmed Gmail cleanup action and mirror it locally.

    The function deliberately works from explicit email IDs instead of an entire
    suggestion bucket. That keeps the AI assistant review-first: MailMind can
    recommend, but the user chooses exactly what gets archived or marked read.
    """
    unique_ids = list(dict.fromkeys(email_ids))
    if not unique_ids:
        return CleanupActionResult(action=action, requested_count=0, applied_count=0, skipped_count=0, emails=[])

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

    for email in emails:
        account = accounts.get(email.gmail_account_id)
        if account is None:
            skipped_count += 1
            continue

        if account.id not in access_tokens:
            access_tokens[account.id] = client.refresh_access_token(decrypt_value(account.refresh_token_ciphertext))

        remove_labels = _labels_to_remove(action)
        client.modify_message_labels(
            access_tokens[account.id],
            email.gmail_message_id,
            remove_labels=remove_labels,
        )
        _mirror_action_locally(email, action=action, remove_labels=remove_labels)
        applied.append(email)

    db.flush()
    return CleanupActionResult(
        action=action,
        requested_count=len(unique_ids),
        applied_count=len(applied),
        skipped_count=skipped_count,
        emails=applied,
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