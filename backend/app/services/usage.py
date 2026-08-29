from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai_usage import AIUsageLog
from app.models.user import User

TOKEN_CHAR_RATIO = 4


@dataclass(frozen=True)
class AIUsageSummary:
    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    by_feature: dict[str, int]
    by_model: dict[str, int]
    since_days: int


def estimate_tokens(*parts: str | None) -> int:
    text = " ".join(part or "" for part in parts)
    return max(1, round(len(text) / TOKEN_CHAR_RATIO)) if text.strip() else 0


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    input_cost = (input_tokens / 1_000_000) * settings.openai_input_cost_per_1m_tokens
    output_cost = (output_tokens / 1_000_000) * settings.openai_output_cost_per_1m_tokens
    return round(input_cost + output_cost, 8)


def log_ai_usage(
    db: Session,
    *,
    user_id: int,
    feature: str,
    stage: str,
    model_version: str,
    input_tokens: int,
    output_tokens: int,
    email_id: int | None = None,
    thread_id: int | None = None,
) -> AIUsageLog:
    total_tokens = input_tokens + output_tokens
    entry = AIUsageLog(
        user_id=user_id,
        email_id=email_id,
        thread_id=thread_id,
        feature=feature,
        stage=stage,
        model_version=model_version,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimate_cost_usd(input_tokens, output_tokens),
    )
    db.add(entry)
    return entry


def build_ai_usage_summary(db: Session, user: User, since_days: int = 30) -> AIUsageSummary:
    since = datetime.now(UTC) - timedelta(days=since_days)
    rows = list(
        db.scalars(
            select(AIUsageLog).where(
                AIUsageLog.user_id == user.id,
                AIUsageLog.created_at >= since,
            )
        )
    )
    by_feature = _count_by(rows, "feature")
    by_model = _count_by(rows, "model_version")
    return AIUsageSummary(
        total_calls=len(rows),
        total_input_tokens=sum(row.input_tokens for row in rows),
        total_output_tokens=sum(row.output_tokens for row in rows),
        total_tokens=sum(row.total_tokens for row in rows),
        estimated_cost_usd=round(sum(row.estimated_cost_usd for row in rows), 8),
        by_feature=by_feature,
        by_model=by_model,
        since_days=since_days,
    )


def count_ai_usage_logs(db: Session, user: User) -> int:
    return int(db.scalar(select(func.count(AIUsageLog.id)).where(AIUsageLog.user_id == user.id)) or 0)


def _count_by(rows: list[AIUsageLog], attr: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(getattr(row, attr))
        counts[key] = counts.get(key, 0) + 1
    return counts