from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import logging
import re

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.classification import EmailClassification
from app.models.gmail import Email, EmailThread
from app.models.user import User
from app.services.spam_detection import detect_spam_fields
from app.services.usage import estimate_tokens, log_ai_usage

logger = logging.getLogger(__name__)

# Constants and patterns used for email classification, including categories, priorities, stages, model versions, and regex patterns for identifying automated senders and questions in email content. 

# These constants are used throughout the classification process to determine the appropriate category, priority, and reply needs for each email.

CATEGORIES = ["primary", "promotions", "social", "updates", "spam"]
PRIORITIES = ["high", "medium", "low"]

STAGE_RULE = "rule"
STAGE_LLM = "llm"
STAGE_LIGHTWEIGHT = "lightweight"

RULE_MODEL_VERSION = "rule-engine-v1"
LIGHTWEIGHT_MODEL_VERSION = "lightweight-v1"

_SENDER_AUTOMATED_PATTERN = re.compile(
    r"no-?reply|notifications?|newsletter|updates@|billing@|receipts?@|do-?not-?reply", re.IGNORECASE
)
_QUESTION_PATTERN = re.compile(r"\?")

_PROMO_KEYWORDS = ["% off", "sale", "discount", "unsubscribe", "limited time", "deal", "coupon", "clearance"]
_SOCIAL_KEYWORDS = [
    "commented on",
    "tagged you",
    "friend request",
    "new follower",
    "liked your",
    "mentioned you",
]
_UPDATE_KEYWORDS = [
    "receipt",
    "invoice",
    "order confirmed",
    "shipped",
    "statement",
    "payment received",
    "your bill",
    "delivery",
    "confirmation",
]
_SPAM_KEYWORDS = [
    "you've won",
    "you have won",
    "claim your prize",
    "act now",
    "wire transfer",
    "verify your account immediately",
    "lottery",
    "urgent bank",
]
_IMPORTANT_KEYWORDS = [
    "interview",
    "urgent",
    "action required",
    "deadline",
    "contract",
    "offer letter",
    "meeting request",
    "please respond",
    "reminder:",
    "rsvp",
]
_REPLY_KEYWORDS = ["please respond", "action required", "rsvp", "let me know", "confirm", "can we", "could you"]

# The _CLASSIFY_SYSTEM_PROMPT is a system prompt used for stage-two classification of emails using an OpenAI-compatible chat completions API. 

# It instructs the model to classify the email and respond with a single JSON object containing keys for category, priority, needs_reply, confidence, and rationale. The prompt specifies the expected values for category and priority based on predefined constants.

_CLASSIFY_SYSTEM_PROMPT = (
    "You are an email triage assistant for an inbox cleaner. Classify the email and reply with a single "
    "JSON object only, no prose, with keys: category (one of "
    f"{CATEGORIES}), priority (one of {PRIORITIES}), needs_reply (true/false), "
    "confidence (0-1 float), rationale (short string)."
)

# The LLMClient class is a wrapper around an OpenAI-compatible chat completions API, used for stage-two classification of emails and thread summaries. It provides methods for classifying email fields and summarizing email threads, handling API requests and responses, and managing configuration settings such as API keys and model selection.

@dataclass
class ClassificationResult:
    category: str
    priority: str
    needs_reply: bool
    confidence: float
    stage: str
    model_version: str
    rationale: str


@dataclass
class ClassificationBatchStats:
    classified_count: int = 0
    by_category: dict[str, int] | None = None
    by_priority: dict[str, int] | None = None
    needs_reply_count: int = 0
    stage_counts: dict[str, int] | None = None

    def __post_init__(self) -> None:
        self.by_category = self.by_category or {}
        self.by_priority = self.by_priority or {}
        self.stage_counts = self.stage_counts or {}


class LLMClient:
    """Wrapper around an OpenAI-compatible chat completions API.

    Used for stage-two classification of emails the rule engine can't
    confidently place, and for thread summaries. When no API key is
    configured, `is_configured` is False and callers fall back to the
    lightweight local classifier/summarizer so the app works fully offline.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = settings.openai_api_key if api_key is None else api_key
        self.model = model or settings.openai_model

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def classify(
        self, subject: str | None, sender: str | None, snippet: str | None, body_preview: str | None
    ) -> dict | None:
        if not self.is_configured:
            return None
        prompt = (
            f"Sender: {sender or 'unknown'}\n"
            f"Subject: {subject or '(no subject)'}\n"
            f"Preview: {(body_preview or snippet or '')[:1000]}"
        )
        try:
            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": _CLASSIFY_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                },
                timeout=20,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception:
            logger.exception("classification.llm_call_failed")
            return None

    def summarize(self, subject: str | None, messages: list[tuple[str | None, str | None]]) -> str | None:
        if not self.is_configured:
            return None
        transcript = "\n".join(f"- {sender or 'unknown'}: {snippet or ''}" for sender, snippet in messages)
        prompt = f"Subject: {subject or '(no subject)'}\nMessages:\n{transcript}\n\nSummarize this email thread in one or two sentences."
        try:
            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You write short, factual email thread summaries."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                },
                timeout=20,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            logger.exception("classification.llm_summary_failed")
            return None


def _combined_text(subject: str | None, snippet: str | None, body_preview: str | None) -> str:
    return " ".join(filter(None, [subject, snippet, body_preview])).lower()


def apply_rule_engine(
    subject: str | None, sender: str | None, snippet: str | None, body_preview: str | None
) -> ClassificationResult | None:
    """Fast, free, deterministic pre-filter. Returns None when the signal is too weak,
    so the caller can escalate to stage two instead of guessing."""
    text = _combined_text(subject, snippet, body_preview)
    sender_l = (sender or "").lower()
    is_automated_sender = bool(_SENDER_AUTOMATED_PATTERN.search(sender_l))

    scores = {category: 0 for category in CATEGORIES}
    if is_automated_sender:
        scores["updates"] += 1
    scores["promotions"] += sum(1 for kw in _PROMO_KEYWORDS if kw in text)
    scores["social"] += sum(1 for kw in _SOCIAL_KEYWORDS if kw in text)
    scores["updates"] += sum(1 for kw in _UPDATE_KEYWORDS if kw in text)
    scores["spam"] += sum(1 for kw in _SPAM_KEYWORDS if kw in text)
    important_hits = sum(1 for kw in _IMPORTANT_KEYWORDS if kw in text)

    best_category = max(scores, key=lambda key: scores[key])
    best_score = scores[best_category]

    if important_hits == 0 and best_score == 0:
        return None

    if important_hits > 0 and important_hits >= best_score:
        category = "primary"
        confidence = min(0.6 + 0.15 * important_hits, 0.95)
    else:
        category = best_category
        confidence = min(0.6 + 0.15 * best_score, 0.95)

    if confidence < settings.classification_rule_confidence_threshold:
        return None

    priority = _infer_priority(category, important_hits, text)
    needs_reply = _infer_needs_reply(category, text, is_automated_sender)

    return ClassificationResult(
        category=category,
        priority=priority,
        needs_reply=needs_reply,
        confidence=round(confidence, 2),
        stage=STAGE_RULE,
        model_version=RULE_MODEL_VERSION,
        rationale=f"Rule engine matched strong '{category}' signals.",
    )


def apply_lightweight_classifier(
    subject: str | None, sender: str | None, snippet: str | None, body_preview: str | None
) -> ClassificationResult:
    """Local, dependency-free fallback for stage two. Always returns a result
    (with softer confidence) so the pipeline terminates even without an LLM key."""
    text = _combined_text(subject, snippet, body_preview)
    sender_l = (sender or "").lower()
    is_automated_sender = bool(_SENDER_AUTOMATED_PATTERN.search(sender_l))

    scores = {category: 0 for category in CATEGORIES}
    if is_automated_sender:
        scores["updates"] += 1
    scores["promotions"] += sum(1 for kw in _PROMO_KEYWORDS if kw in text)
    scores["social"] += sum(1 for kw in _SOCIAL_KEYWORDS if kw in text)
    scores["updates"] += sum(1 for kw in _UPDATE_KEYWORDS if kw in text)
    scores["spam"] += sum(1 for kw in _SPAM_KEYWORDS if kw in text)
    important_hits = sum(1 for kw in _IMPORTANT_KEYWORDS if kw in text)

    best_category = max(scores, key=lambda key: scores[key])
    best_score = scores[best_category]

    if important_hits > 0 and important_hits >= best_score:
        category = "primary"
    elif best_score > 0:
        category = best_category
    else:
        category = "primary"

    confidence = round(min(0.5 + 0.08 * max(best_score, important_hits), 0.7), 2)
    priority = _infer_priority(category, important_hits, text)
    needs_reply = _infer_needs_reply(category, text, is_automated_sender)

    return ClassificationResult(
        category=category,
        priority=priority,
        needs_reply=needs_reply,
        confidence=confidence,
        stage=STAGE_LIGHTWEIGHT,
        model_version=LIGHTWEIGHT_MODEL_VERSION,
        rationale=f"Lightweight fallback scored '{category}' as the closest match.",
    )


def _infer_priority(category: str, important_hits: int, text: str) -> str:
    if category == "primary":
        return "high" if important_hits >= 2 else "medium"
    if category == "updates":
        return "medium" if any(kw in text for kw in ("invoice", "bill", "payment", "statement")) else "low"
    return "low"


def _infer_needs_reply(category: str, text: str, is_automated_sender: bool) -> bool:
    if is_automated_sender or category in ("promotions", "social", "spam", "updates"):
        return False
    if _QUESTION_PATTERN.search(text) or any(kw in text for kw in _REPLY_KEYWORDS):
        return True
    return category == "primary"


def _result_from_llm_payload(payload: dict, model: str) -> ClassificationResult | None:
    try:
        category = str(payload["category"]).strip().lower()
        priority = str(payload["priority"]).strip().lower()
        if category not in CATEGORIES or priority not in PRIORITIES:
            return None
        return ClassificationResult(
            category=category,
            priority=priority,
            needs_reply=bool(payload.get("needs_reply", False)),
            confidence=max(0.0, min(float(payload.get("confidence", 0.7)), 1.0)),
            stage=STAGE_LLM,
            model_version=f"openai:{model}",
            rationale=str(payload.get("rationale", ""))[:500],
        )
    except (KeyError, TypeError, ValueError):
        logger.warning("classification.llm_payload_invalid", extra={"payload": payload})
        return None


def classify_fields(
    subject: str | None,
    sender: str | None,
    snippet: str | None,
    body_preview: str | None,
    llm_client: LLMClient | None = None,
) -> ClassificationResult:
    """Run the two-stage pipeline over raw email fields without touching the DB.
    Used by both the live classifier and the offline evaluation harness."""
    rule_result = apply_rule_engine(subject, sender, snippet, body_preview)
    if rule_result is not None:
        return rule_result

    llm_client = llm_client or LLMClient()
    payload = llm_client.classify(subject, sender, snippet, body_preview)
    if payload:
        llm_result = _result_from_llm_payload(payload, llm_client.model)
        if llm_result is not None:
            return llm_result

    return apply_lightweight_classifier(subject, sender, snippet, body_preview)


def classify_email(db: Session, email: Email, llm_client: LLMClient | None = None) -> EmailClassification:
    result = classify_fields(email.subject, email.sender, email.snippet, email.body_preview, llm_client)
    spam_result = detect_spam_fields(email.subject, email.sender, email.snippet, email.body_preview)
    if spam_result.score >= settings.spam_high_risk_threshold:
        result = ClassificationResult(
            category="spam",
            priority="low",
            needs_reply=False,
            confidence=max(result.confidence, spam_result.score),
            stage=result.stage,
            model_version=f"{result.model_version}+{spam_result.model_version}",
            rationale=f"{result.rationale} Spam detector marked this as high risk.",
        )

    email.spam_label = spam_result.label
    email.spam_score = spam_result.score
    email.spam_model_version = spam_result.model_version
    email.spam_detected_at = datetime.now(UTC)

    email.category = result.category
    email.priority = result.priority
    email.needs_reply = result.needs_reply
    email.classification_confidence = result.confidence
    email.classification_model_version = result.model_version
    email.classified_at = datetime.now(UTC)

    log_entry = EmailClassification(
        email_id=email.id,
        user_id=email.user_id,
        category=result.category,
        priority=result.priority,
        needs_reply=result.needs_reply,
        confidence=result.confidence,
        stage=result.stage,
        model_version=result.model_version,
        rationale=result.rationale,
    )
    db.add(log_entry)

    input_tokens = estimate_tokens(email.subject, email.sender, email.snippet, email.body_preview)
    output_tokens = estimate_tokens(result.category, result.priority, str(result.needs_reply), result.rationale)
    log_ai_usage(
        db,
        user_id=email.user_id,
        email_id=email.id,
        feature="classification",
        stage=result.stage,
        model_version=result.model_version,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    logger.info(
        "classification.completed",
        extra={
            "email_id": email.id,
            "user_id": email.user_id,
            "category": result.category,
            "priority": result.priority,
            "needs_reply": result.needs_reply,
            "confidence": result.confidence,
            "stage": result.stage,
            "model_version": result.model_version,
        },
    )
    return log_entry

def classify_unclassified_emails(
    db: Session,
    user: User,
    llm_client: LLMClient | None = None,
    limit: int | None = None,
) -> ClassificationBatchStats:
    llm_client = llm_client or LLMClient()
    limit = limit or settings.classification_batch_limit
    emails = list(
        db.scalars(
            select(Email)
            .where(Email.user_id == user.id, Email.classified_at.is_(None))
            .order_by(Email.received_at.desc())
            .limit(limit)
        )
    )

    stats = ClassificationBatchStats()
    touched_thread_ids: set[int] = set()
    for email in emails:
        log_entry = classify_email(db, email, llm_client=llm_client)
        stats.classified_count += 1
        stats.by_category[log_entry.category] = stats.by_category.get(log_entry.category, 0) + 1
        stats.by_priority[log_entry.priority] = stats.by_priority.get(log_entry.priority, 0) + 1
        stats.stage_counts[log_entry.stage] = stats.stage_counts.get(log_entry.stage, 0) + 1
        if log_entry.needs_reply:
            stats.needs_reply_count += 1
        touched_thread_ids.add(email.thread_id)

    for thread_id in touched_thread_ids:
        thread = db.get(EmailThread, thread_id)
        if thread is not None:
            summarize_thread(db, thread, llm_client=llm_client)

    db.commit()
    return stats

# extractive summary 
def _extractive_summary(subject: str | None, messages: list[Email]) -> str:
    latest = messages[-1]
    preview = latest.snippet or subject or "No preview available."
    if len(messages) == 1:
        return f"{latest.sender or 'Unknown sender'}: {preview}"
    return f"{len(messages)} messages in this thread. Latest from {latest.sender or 'unknown sender'}: {preview}"


def summarize_thread(db: Session, thread: EmailThread, llm_client: LLMClient | None = None) -> EmailThread:
    messages = list(
        db.scalars(
            select(Email).where(Email.thread_id == thread.id).order_by(Email.received_at.asc(), Email.id.asc())
        )
    )
    if not messages:
        return thread

    llm_client = llm_client or LLMClient()
    summary = llm_client.summarize(thread.subject, [(m.sender, m.snippet) for m in messages])
    model_version = f"openai:{llm_client.model}" if summary else LIGHTWEIGHT_MODEL_VERSION
    if not summary:
        summary = _extractive_summary(thread.subject, messages)

    input_tokens = estimate_tokens(thread.subject, *(message.snippet for message in messages))
    output_tokens = estimate_tokens(summary)
    log_ai_usage(
        db,
        user_id=thread.user_id,
        thread_id=thread.id,
        feature="thread_summary",
        stage="llm" if model_version.startswith("openai:") else STAGE_LIGHTWEIGHT,
        model_version=model_version,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    thread.summary = summary
    thread.summary_model_version = model_version
    thread.summarized_at = datetime.now(UTC)
    return thread