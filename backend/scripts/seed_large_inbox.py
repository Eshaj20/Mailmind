"""Seed a large synthetic inbox for scalability benchmarks.

Usage from backend/:
    python -m scripts.seed_large_inbox --count 10000 --reset

The generated data is synthetic and safe for public demos. It exercises the
same user/account/thread/email models as Gmail sync, then runs the same local
classification, spam-risk, and search-indexing pipeline without calling Google
or OpenAI.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import random
import time
from typing import Iterable

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_value
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.ai_usage import AIUsageLog
from app.models.classification import EmailClassification
from app.models.cleanup_action import CleanupActionLog
from app.models.feedback import EmailFeedback
from app.models.gmail import Email, EmailThread, GmailAccount
from app.models.sync_job import SyncJob
from app.models.user import User
from app.services.classification import LLMClient, classify_email
from app.services.search import ensure_email_search_index

LARGE_EMAIL = "large@mailmind.dev"
LARGE_PASSWORD = "LargePass123!"
LARGE_GMAIL = "large.inbox@mailmind.dev"
LARGE_ACCOUNT_TOKEN = "large-inbox-refresh-token-not-real"


@dataclass(frozen=True)
class LargeInboxTemplate:
    sender: str
    subject: str
    body: str
    labels: list[str]


TEMPLATES: tuple[LargeInboxTemplate, ...] = (
    LargeInboxTemplate(
        "Recruiter <recruiter@talenthub.example>",
        "Backend Engineer interview schedule",
        "Can we schedule your backend interview this week? Please reply with your availability.",
        ["INBOX", "UNREAD"],
    ),
    LargeInboxTemplate(
        "Deals <offers@shop.example>",
        "Limited time sale and discount coupon",
        "Your saved item is on sale. Use this coupon before midnight. Unsubscribe from deal alerts.",
        ["INBOX", "CATEGORY_PROMOTIONS"],
    ),
    LargeInboxTemplate(
        "Electricity Board <billing@utility.example>",
        "Electricity bill invoice is ready",
        "Your electricity bill invoice is ready. Please pay before the due date.",
        ["INBOX"],
    ),
    LargeInboxTemplate(
        "Bank Alerts <alerts@bank.example>",
        "Credit card statement generated",
        "Your monthly statement is generated and payment is due soon.",
        ["INBOX", "UNREAD"],
    ),
    LargeInboxTemplate(
        "LinkedIn <notifications@linkedin.example>",
        "You have new profile views",
        "People viewed your profile and mentioned you in updates this week.",
        ["INBOX", "CATEGORY_SOCIAL"],
    ),
    LargeInboxTemplate(
        "Tech Digest <digest@techweekly.example>",
        "Weekly AI engineering newsletter",
        "This newsletter covers retrieval, model evaluation, monitoring, and production AI systems. Unsubscribe here.",
        ["INBOX", "CATEGORY_PROMOTIONS"],
    ),
    LargeInboxTemplate(
        "Support <support@saas.example>",
        "Action required for your account",
        "Please confirm your workspace settings so we can complete the migration.",
        ["INBOX", "UNREAD"],
    ),
    LargeInboxTemplate(
        "Travel Desk <alerts@travel.example>",
        "Flight ticket confirmation",
        "Your flight booking is confirmed. Download itinerary and boarding details.",
        ["INBOX"],
    ),
    LargeInboxTemplate(
        "Prize Desk <winner@unknown.example>",
        "You have won a cash reward",
        "Claim your urgent prize now. Verify your account immediately to receive the reward.",
        ["INBOX", "SPAM"],
    ),
    LargeInboxTemplate(
        "No Reply <no-reply@product.example>",
        "Product update and release notes",
        "Your product workspace has new updates and release notes available.",
        ["INBOX"],
    ),
)


def _get_or_create_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == LARGE_EMAIL))
    if user is None:
        user = User(
            email=LARGE_EMAIL,
            full_name="MailMind Large Inbox User",
            hashed_password=hash_password(LARGE_PASSWORD),
        )
        db.add(user)
        db.flush()
    return user


def _get_or_create_account(db: Session, user: User) -> GmailAccount:
    account = db.scalar(
        select(GmailAccount).where(
            GmailAccount.user_id == user.id,
            GmailAccount.google_email == LARGE_GMAIL,
        )
    )
    if account is None:
        account = GmailAccount(
            user_id=user.id,
            google_email=LARGE_GMAIL,
            refresh_token_ciphertext=encrypt_value(LARGE_ACCOUNT_TOKEN),
            scopes=["synthetic", "gmail.readonly"],
            history_id="large-history-0",
            sync_status="connected",
            last_synced_at=datetime.now(UTC),
        )
        db.add(account)
        db.flush()
    return account


def _delete_large_inbox_data(db: Session, user: User) -> None:
    email_ids = select(Email.id).where(Email.user_id == user.id)
    db.execute(delete(CleanupActionLog).where(CleanupActionLog.user_id == user.id))
    db.execute(delete(EmailFeedback).where(EmailFeedback.email_id.in_(email_ids)))
    db.execute(delete(EmailClassification).where(EmailClassification.user_id == user.id))
    db.execute(delete(AIUsageLog).where(AIUsageLog.user_id == user.id))
    db.execute(delete(SyncJob).where(SyncJob.user_id == user.id))
    db.execute(delete(Email).where(Email.user_id == user.id))
    db.execute(delete(EmailThread).where(EmailThread.user_id == user.id))
    db.execute(delete(GmailAccount).where(GmailAccount.user_id == user.id, GmailAccount.google_email == LARGE_GMAIL))
    db.flush()


def _subject(template: LargeInboxTemplate, index: int) -> str:
    month = (index % 12) + 1
    return f"{template.subject} #{index + 1} / 2026-{month:02d}"


def _body(template: LargeInboxTemplate, index: int) -> str:
    account_token = f"workspace-{index % 37}"
    return (
        f"{template.body} Synthetic benchmark row {index + 1}. "
        f"Mailbox cluster {account_token}. This is safe demo data."
    )


def _create_large_emails(db: Session, user: User, account: GmailAccount, count: int, batch_size: int) -> int:
    created = 0
    now = datetime.now(UTC)
    rng = random.Random(20260831)

    for index in range(count):
        template = TEMPLATES[index % len(TEMPLATES)]
        gmail_thread_id = f"large-thread-{index // 4}"
        gmail_message_id = f"large-msg-{index + 1}"

        existing = db.scalar(
            select(Email.id).where(
                Email.gmail_account_id == account.id,
                Email.gmail_message_id == gmail_message_id,
            )
        )
        if existing is not None:
            continue

        received_at = now - timedelta(minutes=index * 17 + rng.randint(0, 15))
        thread = db.scalar(
            select(EmailThread).where(
                EmailThread.gmail_account_id == account.id,
                EmailThread.gmail_thread_id == gmail_thread_id,
            )
        )
        if thread is None:
            thread = EmailThread(
                user_id=user.id,
                gmail_account_id=account.id,
                gmail_thread_id=gmail_thread_id,
                subject=_subject(template, index),
                snippet=template.body[:180],
                last_message_at=received_at,
            )
            db.add(thread)
            db.flush()
        else:
            thread.last_message_at = max(thread.last_message_at or received_at, received_at)

        labels = list(template.labels)
        if index % 11 == 0 and "UNREAD" not in labels:
            labels.append("UNREAD")

        email = Email(
            user_id=user.id,
            gmail_account_id=account.id,
            thread_id=thread.id,
            gmail_message_id=gmail_message_id,
            sender=template.sender,
            recipients=LARGE_GMAIL,
            subject=_subject(template, index),
            snippet=template.body[:220],
            body_preview=_body(template, index),
            labels=labels,
            is_read="UNREAD" not in labels,
            received_at=received_at,
        )
        ensure_email_search_index(email)
        db.add(email)
        created += 1

        if created % batch_size == 0:
            db.flush()

    db.flush()
    return created


def _classify_large_emails(db: Session, user: User, batch_size: int) -> int:
    """Classify seeded emails without summarizing every thread.

    The product batch classifier also creates thread summaries. For a 10k+
    benchmark that can dominate runtime, so this path focuses on the email-level
    cleanup signals: category, priority, needs_reply, spam risk, and audit logs.
    """
    llm_client = LLMClient(api_key="")
    classified = 0

    while True:
        emails = list(
            db.scalars(
                select(Email)
                .where(Email.user_id == user.id, Email.classified_at.is_(None))
                .order_by(Email.received_at.desc())
                .limit(batch_size)
            )
        )
        if not emails:
            break
        for email in emails:
            classify_email(db, email, llm_client=llm_client)
            ensure_email_search_index(email)
            classified += 1
        db.commit()

    return classified


def seed_large_inbox(
    db: Session,
    count: int = 10000,
    reset: bool = False,
    batch_size: int = 500,
    classify: bool = True,
) -> dict[str, int | str | float]:
    started_at = time.perf_counter()
    user = _get_or_create_user(db)
    if reset:
        _delete_large_inbox_data(db, user)
        user = _get_or_create_user(db)

    account = _get_or_create_account(db, user)
    created_count = _create_large_emails(db, user, account, count, batch_size)
    account.history_id = f"large-history-{count}"
    account.last_synced_at = datetime.now(UTC)
    db.add(
        SyncJob(
            user_id=user.id,
            gmail_account_id=account.id,
            job_type="large_inbox_seed",
            status="succeeded",
            attempt_count=1,
            max_attempts=1,
            max_results=count,
            synced_count=count,
            created_count=created_count,
            updated_count=max(0, count - created_count),
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
        )
    )
    db.commit()

    classified_count = _classify_large_emails(db, user, batch_size) if classify else 0
    total_count = db.scalar(select(func.count()).select_from(Email).where(Email.user_id == user.id)) or 0
    elapsed_seconds = round(time.perf_counter() - started_at, 3)

    return {
        "email": LARGE_EMAIL,
        "password": LARGE_PASSWORD,
        "gmail_account": LARGE_GMAIL,
        "target_count": count,
        "total_count": int(total_count),
        "created_count": created_count,
        "classified_count": classified_count,
        "elapsed_seconds": elapsed_seconds,
    }


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=10000, help="Number of synthetic emails to seed")
    parser.add_argument("--batch-size", type=int, default=500, help="Flush/classify batch size")
    parser.add_argument("--reset", action="store_true", help="Delete and recreate the large synthetic inbox first")
    parser.add_argument("--skip-classify", action="store_true", help="Only seed emails, without classification")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.count < 1:
        raise SystemExit("--count must be at least 1")
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be at least 1")

    db = SessionLocal()
    try:
        result = seed_large_inbox(
            db,
            count=args.count,
            reset=args.reset,
            batch_size=args.batch_size,
            classify=not args.skip_classify,
        )
    finally:
        db.close()

    print("Seeded MailMind large synthetic inbox")
    print(f"  login: {result['email']}")
    print(f"  password: {result['password']}")
    print(f"  gmail account: {result['gmail_account']}")
    print(f"  target emails: {result['target_count']}")
    print(f"  total emails: {result['total_count']}")
    print(f"  new emails created: {result['created_count']}")
    print(f"  emails classified this run: {result['classified_count']}")
    print(f"  elapsed seconds: {result['elapsed_seconds']}")


if __name__ == "__main__":
    main()