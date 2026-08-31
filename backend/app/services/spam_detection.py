from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from app.core.config import settings

SPAM_MODEL_VERSION = "spam-detector-v1"
HEURISTIC_MODEL_VERSION = "spam-heuristic-v1"

_HIGH_RISK_PATTERNS = [
    r"claim\s+(your\s+)?(prize|reward|gift)",
    r"you\s+(have\s+)?won",
    r"urgent\s+(bank|account|verification)",
    r"verify\s+your\s+account\s+immediately",
    r"wire\s+transfer",
    r"lottery",
    r"suspicious\s+link",
    r"account\s+will\s+be\s+suspended",
]
_MEDIUM_RISK_PATTERNS = [
    r"act\s+now",
    r"limited\s+time",
    r"click\s+here",
    r"risk-free",
    r"free\s+(gift|iphone|cash|crypto)",
    r"unsubscribe",
    r"winner",
]
_TRUSTED_PATTERNS = [
    r"interview",
    r"meeting",
    r"invoice",
    r"statement",
    r"receipt",
    r"security\s+alert",
    r"github",
]


@dataclass(frozen=True)
class SpamDetectionResult:
    label: str
    score: float
    model_version: str
    rationale: str


_MODEL_CACHE: dict[str, Any] = {}


def detect_spam_fields(
    subject: str | None,
    sender: str | None,
    snippet: str | None,
    body_preview: str | None,
) -> SpamDetectionResult:
    """Return a spam probability for an email.

    Production deployments can point SPAM_MODEL_PATH at a pretrained sklearn/joblib
    model. Local tests and demo mode use the deterministic heuristic fallback, so
    MailMind never depends on downloading private or paid model assets at runtime.
    """
    text = _email_text(subject, sender, snippet, body_preview)
    pretrained = _predict_with_pretrained_model(text)
    if pretrained is not None:
        return pretrained
    return _predict_with_heuristics(text)


def _email_text(subject: str | None, sender: str | None, snippet: str | None, body_preview: str | None) -> str:
    return "\n".join(part or "" for part in [sender, subject, snippet, body_preview]).strip()


def _predict_with_pretrained_model(text: str) -> SpamDetectionResult | None:
    model_path = settings.spam_model_path.strip()
    if not model_path:
        return None

    path = Path(model_path)
    if not path.exists():
        return None

    model = _MODEL_CACHE.get(str(path))
    if model is None:
        try:
            import joblib  # type: ignore[import-not-found]

            model = joblib.load(path)
            _MODEL_CACHE[str(path)] = model
        except Exception:
            return None

    try:
        if hasattr(model, "predict_proba"):
            probabilities = model.predict_proba([text])[0]
            classes = [str(value).lower() for value in getattr(model, "classes_", [])]
            spam_index = classes.index("spam") if "spam" in classes else len(probabilities) - 1
            score = float(probabilities[spam_index])
        else:
            prediction = str(model.predict([text])[0]).lower()
            score = 0.9 if prediction == "spam" else 0.1
    except Exception:
        return None

    score = round(max(0.0, min(score, 1.0)), 4)
    return SpamDetectionResult(
        label="spam" if score >= settings.spam_score_threshold else "ham",
        score=score,
        model_version=settings.spam_model_version or SPAM_MODEL_VERSION,
        rationale="Pretrained local spam model prediction.",
    )


def _predict_with_heuristics(text: str) -> SpamDetectionResult:
    lowered = text.lower()
    high_hits = _count_matches(_HIGH_RISK_PATTERNS, lowered)
    medium_hits = _count_matches(_MEDIUM_RISK_PATTERNS, lowered)
    trusted_hits = _count_matches(_TRUSTED_PATTERNS, lowered)

    score = 0.08 + high_hits * 0.26 + medium_hits * 0.11 - trusted_hits * 0.05
    if "spam" in lowered:
        score += 0.15
    score = round(max(0.0, min(score, 0.98)), 4)
    label = "spam" if score >= settings.spam_score_threshold else "ham"

    return SpamDetectionResult(
        label=label,
        score=score,
        model_version=HEURISTIC_MODEL_VERSION,
        rationale=f"Heuristic spam score from {high_hits} high-risk and {medium_hits} medium-risk signals.",
    )


def _count_matches(patterns: list[str], text: str) -> int:
    return sum(1 for pattern in patterns if re.search(pattern, text, re.IGNORECASE))