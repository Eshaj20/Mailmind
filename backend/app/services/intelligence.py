from __future__ import annotations

from dataclasses import dataclass
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.gmail import Email
from app.models.user import User

NEWSLETTER_PATTERN = re.compile(r"\b(unsubscribe|newsletter|digest|sale|offer|promotion|coupon)\b", re.I)
CANDIDATE_EMAIL_LIMIT = 5
SENDER_BREAKDOWN_LIMIT = 5


@dataclass(frozen=True)
class SenderBreakdown:
    sender: str
    count: int


@dataclass(frozen=True)
class CleanupSuggestion:
    suggestion_type: str
    title: str
    description: str
    email_count: int
    estimated_time_saved_minutes: int
    confidence: float
    candidate_emails: list[Email]
    sender_breakdown: list[SenderBreakdown]


@dataclass(frozen=True)
class InboxHealth:
    score: int
    total_emails: int
    unread_count: int
    high_priority_unread_count: int
    pending_reply_count: int
    cleanup_candidate_count: int
    formula: str
    suggestions: list[CleanupSuggestion]


def build_inbox_health(db: Session, user: User) -> InboxHealth:
    emails = list(db.scalars(select(Email).where(Email.user_id == user.id)))
    total = len(emails)
    unread = [email for email in emails if not email.is_read]
    high_priority_unread = [email for email in unread if (email.priority or "").lower() == "high"]
    pending_reply = [email for email in emails if email.needs_reply is True]
    cleanup_candidates = [email for email in emails if _is_cleanup_candidate(email)]

    unread_ratio = len(unread) / total if total else 0.0
    cleanup_ratio = len(cleanup_candidates) / total if total else 0.0
    pending_ratio = len(pending_reply) / total if total else 0.0

    score = 100
    score -= round(unread_ratio * 30)
    score -= min(len(high_priority_unread) * 8, 24)
    score -= round(pending_ratio * 25)
    score -= round(cleanup_ratio * 20)
    score = max(0, min(100, score))

    return InboxHealth(
        score=score,
        total_emails=total,
        unread_count=len(unread),
        high_priority_unread_count=len(high_priority_unread),
        pending_reply_count=len(pending_reply),
        cleanup_candidate_count=len(cleanup_candidates),
        formula=(
            "100 - unread_ratio*30 - high_priority_unread*8 "
            "- pending_reply_ratio*25 - cleanup_candidate_ratio*20"
        ),
        suggestions=_build_cleanup_suggestions(cleanup_candidates, pending_reply, high_priority_unread),
    )


def _build_cleanup_suggestions(
    cleanup_candidates: list[Email],
    pending_reply: list[Email],
    high_priority_unread: list[Email],
) -> list[CleanupSuggestion]:
    suggestions: list[CleanupSuggestion] = []

    if cleanup_candidates:
        suggestions.append(
            CleanupSuggestion(
                suggestion_type="archive_low_value",
                title="Archive low-value newsletters and promotions",
                description="Promotional/newsletter-like emails are good cleanup candidates after review.",
                email_count=len(cleanup_candidates),
                estimated_time_saved_minutes=max(1, round(len(cleanup_candidates) * 0.5)),
                confidence=0.82,
                candidate_emails=_top_candidate_emails(cleanup_candidates),
                sender_breakdown=_sender_breakdown(cleanup_candidates),
            )
        )

    if pending_reply:
        suggestions.append(
            CleanupSuggestion(
                suggestion_type="follow_up",
                title="Review emails that may need a reply",
                description="These messages were classified as needing a response.",
                email_count=len(pending_reply),
                estimated_time_saved_minutes=max(1, len(pending_reply)),
                confidence=0.78,
                candidate_emails=_top_candidate_emails(pending_reply),
                sender_breakdown=_sender_breakdown(pending_reply),
            )
        )

    if high_priority_unread:
        suggestions.append(
            CleanupSuggestion(
                suggestion_type="read_priority",
                title="Read high-priority unread emails first",
                description="High-priority unread messages should be handled before bulk cleanup.",
                email_count=len(high_priority_unread),
                estimated_time_saved_minutes=max(1, len(high_priority_unread)),
                confidence=0.9,
                candidate_emails=_top_candidate_emails(high_priority_unread),
                sender_breakdown=_sender_breakdown(high_priority_unread),
            )
        )

    return suggestions


def _top_candidate_emails(emails: list[Email]) -> list[Email]:
    return sorted(emails, key=lambda email: email.received_at or email.created_at, reverse=True)[:CANDIDATE_EMAIL_LIMIT]


def _sender_breakdown(emails: list[Email]) -> list[SenderBreakdown]:
    counts: dict[str, int] = {}
    for email in emails:
        sender = email.sender or "Unknown sender"
        counts[sender] = counts.get(sender, 0) + 1
    return [
        SenderBreakdown(sender=sender, count=count)
        for sender, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:SENDER_BREAKDOWN_LIMIT]
    ]


def _is_cleanup_candidate(email: Email) -> bool:
    category = (email.category or "").lower()
    priority = (email.priority or "").lower()
    text = " ".join(part or "" for part in [email.sender, email.subject, email.snippet, email.body_preview])
    return (
        category in {"promotions", "social", "spam"}
        or NEWSLETTER_PATTERN.search(text) is not None
        or (category == "updates" and priority == "low")
    )
