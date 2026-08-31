"""Seed a realistic demo inbox without Google OAuth or real Gmail data.

Usage from backend/:
    python -m scripts.seed_demo_inbox
    python -m scripts.seed_demo_inbox --count 150 --reset

This is intended for portfolio demos and deployed preview environments where
recruiters should see the complete MailMind flow without connecting a personal
Gmail account or requiring Google Cloud billing details.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import random
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_value
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.classification import EmailClassification
from app.models.cleanup_action import CleanupActionLog
from app.models.feedback import EmailFeedback
from app.models.gmail import Email, EmailThread, GmailAccount
from app.models.sync_job import SyncJob
from app.models.ai_usage import AIUsageLog
from app.models.user import User
from app.services.classification import LLMClient, classify_unclassified_emails
from app.services.search import ensure_email_search_index

DEMO_EMAIL = "demo@mailmind.dev"
DEMO_PASSWORD = "DemoPass123!"
DEMO_GMAIL = "demo.inbox@mailmind.dev"
DEMO_ACCOUNT_TOKEN = "demo-refresh-token-not-real"


@dataclass(frozen=True)
class DemoTemplate:
    sender: str
    subject: str
    body: str
    labels: list[str]
    category_hint: str


TEMPLATES: tuple[DemoTemplate, ...] = (
    DemoTemplate(
        "Recruiter <recruiter@talenthub.example>",
        "Backend Engineer interview schedule",
        "Can we schedule your backend interview this week? Please reply with your availability.",
        ["INBOX", "UNREAD"],
        "primary",
    ),
    DemoTemplate(
        "Amazon Deals <deals@amazon.example>",
        "Limited time sale on headphones",
        "Your saved item is now on discount. Offer ends tonight. Unsubscribe from promotional alerts anytime.",
        ["INBOX", "CATEGORY_PROMOTIONS"],
        "promotions",
    ),
    DemoTemplate(
        "Electricity Board <billing@utility.example>",
        "Electricity bill for August is ready",
        "Your electricity bill invoice is ready. Pay before the due date to avoid late fees.",
        ["INBOX"],
        "updates",
    ),
    DemoTemplate(
        "LinkedIn <notifications@linkedin.example>",
        "You have new profile views",
        "People are viewing your profile. See who checked your profile this week.",
        ["INBOX", "CATEGORY_SOCIAL"],
        "social",
    ),
    DemoTemplate(
        "Flight Alerts <alerts@travel.example>",
        "Flight ticket confirmation DEL to BLR",
        "Your flight booking is confirmed. Download your itinerary and boarding details.",
        ["INBOX"],
        "updates",
    ),
    DemoTemplate(
        "Bank Alerts <alerts@bank.example>",
        "Credit card statement generated",
        "Your monthly credit card statement is generated. Minimum amount due is listed in the statement.",
        ["INBOX", "UNREAD"],
        "updates",
    ),
    DemoTemplate(
        "GitHub <noreply@github.example>",
        "Security alert for repository dependency",
        "A dependency in your repository has a security vulnerability. Review the advisory and update soon.",
        ["INBOX", "UNREAD"],
        "updates",
    ),
    DemoTemplate(
        "Founder <founder@startup.example>",
        "Follow up on product discussion",
        "Following up on our previous discussion. Could you send the revised architecture notes?",
        ["INBOX", "UNREAD"],
        "primary",
    ),
    DemoTemplate(
        "Newsletter <digest@techweekly.example>",
        "Weekly AI engineering digest",
        "This week in AI infrastructure, retrieval, model evaluation, and production monitoring. Unsubscribe here.",
        ["INBOX", "CATEGORY_PROMOTIONS"],
        "promotions",
    ),
    DemoTemplate(
        "Prize Desk <winner@unknown.example>",
        "You won a cash reward",
        "Claim your urgent reward now. Click the suspicious link and verify your account immediately.",
        ["INBOX", "SPAM"],
        "spam",
    ),
)


def _demo_subject(template: DemoTemplate, index: int) -> str:
    if index < len(TEMPLATES):
        return template.subject
    return f"{template.subject} #{index + 1}"


def _demo_body(template: DemoTemplate, index: int) -> str:
    variants = [
        "This message is part of the demo inbox used for MailMind portfolio testing.",
        "It helps validate classification, hybrid search, cleanup preview, and sender intelligence.",
        "The content is synthetic and safe to expose in screenshots or live demos.",
    ]
    return f"{template.body} {variants[index % len(variants)]}"


def _get_or_create_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is None:
        user = User(
            email=DEMO_EMAIL,
            full_name="MailMind Demo User",
            hashed_password=hash_password(DEMO_PASSWORD),
        )
        db.add(user)
        db.flush()
    return user


def _get_or_create_account(db: Session, user: User) -> GmailAccount:
    account = db.scalar(
        select(GmailAccount).where(
            GmailAccount.user_id == user.id,
            GmailAccount.google_email == DEMO_GMAIL,
        )
    )
    if account is None:
        account = GmailAccount(
            user_id=user.id,
            google_email=DEMO_GMAIL,
            refresh_token_ciphertext=encrypt_value(DEMO_ACCOUNT_TOKEN),
            scopes=["demo", "gmail.readonly"],
            history_id="demo-history-0",
            sync_status="connected",
            last_synced_at=datetime.now(UTC),
        )
        db.add(account)
        db.flush()
    return account


def _delete_demo_data(db: Session, user: User) -> None:
    db.execute(delete(CleanupActionLog).where(CleanupActionLog.user_id == user.id))
    db.execute(delete(EmailFeedback).where(EmailFeedback.email_id.in_(select(Email.id).where(Email.user_id == user.id))))
    db.execute(delete(EmailClassification).where(EmailClassification.user_id == user.id))
    db.execute(delete(AIUsageLog).where(AIUsageLog.user_id == user.id))
    db.execute(delete(SyncJob).where(SyncJob.user_id == user.id))
    db.execute(delete(Email).where(Email.user_id == user.id))
    db.execute(delete(EmailThread).where(EmailThread.user_id == user.id))
    db.execute(delete(GmailAccount).where(GmailAccount.user_id == user.id, GmailAccount.google_email == DEMO_GMAIL))
    db.flush()


def _create_demo_emails(db: Session, user: User, account: GmailAccount, count: int) -> int:
    created = 0
    now = datetime.now(UTC)
    rng = random.Random(42)

    for index in range(count):
        template = TEMPLATES[index % len(TEMPLATES)]
        gmail_thread_id = f"demo-thread-{index // 3}"
        gmail_message_id = f"demo-msg-{index + 1}"

        existing = db.scalar(
            select(Email).where(
                Email.gmail_account_id == account.id,
                Email.gmail_message_id == gmail_message_id,
            )
        )
        if existing is not None:
            continue

        received_at = now - timedelta(hours=index * 3 + rng.randint(0, 2))
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
                subject=_demo_subject(template, index),
                snippet=template.body[:180],
                last_message_at=received_at,
            )
            db.add(thread)
            db.flush()
        else:
            thread.last_message_at = max(thread.last_message_at or received_at, received_at)

        labels = list(template.labels)
        if index % 7 == 0 and "UNREAD" not in labels:
            labels.append("UNREAD")
        email = Email(
            user_id=user.id,
            gmail_account_id=account.id,
            thread_id=thread.id,
            gmail_message_id=gmail_message_id,
            sender=template.sender,
            recipients=DEMO_GMAIL,
            subject=_demo_subject(template, index),
            snippet=template.body[:220],
            body_preview=_demo_body(template, index),
            labels=labels,
            is_read="UNREAD" not in labels,
            received_at=received_at,
        )
        ensure_email_search_index(email)
        db.add(email)
        created += 1

    db.flush()
    return created


def _create_demo_sync_job(db: Session, user: User, account: GmailAccount, count: int, created_count: int) -> None:
    db.add(
        SyncJob(
            user_id=user.id,
            gmail_account_id=account.id,
            job_type="demo_seed",
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


def seed_demo_inbox(db: Session, count: int = 150, reset: bool = False) -> dict[str, int | str]:
    user = _get_or_create_user(db)
    if reset:
        _delete_demo_data(db, user)
        user = _get_or_create_user(db)
    account = _get_or_create_account(db, user)
    created_count = _create_demo_emails(db, user, account, count)
    db.commit()

    stats = classify_unclassified_emails(db, user, llm_client=LLMClient(api_key=""), limit=count)
    account.history_id = f"demo-history-{count}"
    account.last_synced_at = datetime.now(UTC)
    _create_demo_sync_job(db, user, account, count, created_count)
    db.commit()

    return {
        "email": DEMO_EMAIL,
        "password": DEMO_PASSWORD,
        "gmail_account": DEMO_GMAIL,
        "target_count": count,
        "created_count": created_count,
        "classified_count": stats.classified_count,
    }


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=150, help="Number of synthetic demo emails to seed")
    parser.add_argument("--reset", action="store_true", help="Delete and recreate demo inbox data before seeding")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.count < 1:
        raise SystemExit("--count must be at least 1")

    db = SessionLocal()
    try:
        result = seed_demo_inbox(db, count=args.count, reset=args.reset)
    finally:
        db.close()

    print("Seeded MailMind demo inbox")
    print(f"  login: {result['email']}")
    print(f"  password: {result['password']}")
    print(f"  gmail account: {result['gmail_account']}")
    print(f"  target emails: {result['target_count']}")
    print(f"  new emails created: {result['created_count']}")
    print(f"  emails classified this run: {result['classified_count']}")


if __name__ == "__main__":
    main()