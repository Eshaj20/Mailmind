"""Benchmark MailMind on a large synthetic inbox.

Usage from backend/:
    python -m scripts.benchmark_large_inbox --seed-count 10000 --reset

The benchmark records product-level signals that matter for a real Gmail
cleaner: classification coverage, spam-risk volume, cleanup candidates, inbox
health latency, cleanup preview latency, and search latency across retrieval
modes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import time
from typing import Any, Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.gmail import Email
from app.models.user import User
from app.services.intelligence import build_cleanup_preview, build_inbox_health
from app.services.search import ensure_user_search_index, search_emails_by_mode
from scripts.seed_large_inbox import LARGE_EMAIL, seed_large_inbox

SEARCH_QUERIES = (
    "interview schedule",
    "electricity bill",
    "discount coupon",
    "credit card statement",
    "cash reward verify account",
)
SEARCH_MODES = ("keyword", "vector", "hybrid")


def _measure_ms(callback) -> tuple[Any, float]:
    started_at = time.perf_counter()
    result = callback()
    return result, round((time.perf_counter() - started_at) * 1000, 3)


def _count_emails(db: Session, user: User) -> dict[str, int]:
    total = db.scalar(select(func.count()).select_from(Email).where(Email.user_id == user.id)) or 0
    classified = (
        db.scalar(select(func.count()).select_from(Email).where(Email.user_id == user.id, Email.classified_at.is_not(None)))
        or 0
    )
    spam_risk = (
        db.scalar(select(func.count()).select_from(Email).where(Email.user_id == user.id, Email.spam_score >= 0.7)) or 0
    )
    unread = db.scalar(select(func.count()).select_from(Email).where(Email.user_id == user.id, Email.is_read.is_(False))) or 0
    return {
        "total_emails": int(total),
        "classified_emails": int(classified),
        "spam_risk_emails": int(spam_risk),
        "unread_emails": int(unread),
    }


def _benchmark_search(db: Session, user: User, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for query in SEARCH_QUERIES:
        for mode in SEARCH_MODES:
            results, latency_ms = _measure_ms(
                lambda query=query, mode=mode: search_emails_by_mode(db=db, user=user, query=query, limit=limit, mode=mode)
            )
            rows.append(
                {
                    "query": query,
                    "mode": mode,
                    "latency_ms": latency_ms,
                    "result_count": len(results),
                    "top_subject": results[0].email.subject if results else None,
                    "top_match_reason": results[0].match_reason if results else None,
                }
            )
    return rows


def run_large_inbox_benchmark(
    db: Session,
    user_email: str = LARGE_EMAIL,
    seed_count: int | None = None,
    reset: bool = False,
    batch_size: int = 500,
    search_limit: int = 10,
) -> dict[str, Any]:
    seed_result = None
    if seed_count is not None:
        seed_result = seed_large_inbox(db, count=seed_count, reset=reset, batch_size=batch_size, classify=True)

    user = db.scalar(select(User).where(User.email == user_email))
    if user is None:
        raise SystemExit(f"User not found: {user_email}. Seed first or pass --seed-count.")

    counts = _count_emails(db, user)
    _, index_warmup_latency_ms = _measure_ms(lambda: ensure_user_search_index(db, user))
    health, health_latency_ms = _measure_ms(lambda: build_inbox_health(db, user))
    cleanup_preview, cleanup_latency_ms = _measure_ms(lambda: build_cleanup_preview(db, user, limit=100))
    search_rows = _benchmark_search(db, user, search_limit)
    search_latencies = [row["latency_ms"] for row in search_rows]

    return {
        "user_email": user.email,
        "seed_result": seed_result,
        "counts": counts,
        "search_index": {
            "warmup_latency_ms": index_warmup_latency_ms,
        },
        "inbox_health": {
            "score": health.score,
            "cleanup_candidate_count": health.cleanup_candidate_count,
            "pending_reply_count": health.pending_reply_count,
            "latency_ms": health_latency_ms,
        },
        "cleanup_preview": {
            "total_candidates": cleanup_preview.total_candidates,
            "returned_items": len(cleanup_preview.items),
            "estimated_time_saved_minutes": cleanup_preview.estimated_time_saved_minutes,
            "latency_ms": cleanup_latency_ms,
        },
        "search": {
            "queries": len(SEARCH_QUERIES),
            "modes": list(SEARCH_MODES),
            "avg_latency_ms": round(statistics.mean(search_latencies), 3) if search_latencies else 0.0,
            "p95_latency_ms": _p95(search_latencies),
            "rows": search_rows,
        },
    }


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * 0.95 + 0.999999) - 1))
    return round(ordered[index], 3)


def render_markdown(report: dict[str, Any]) -> str:
    counts = report["counts"]
    lines = ["# Large Inbox Benchmark", ""]
    lines.append("Synthetic benchmark for proving MailMind behavior on a large inbox without exposing private Gmail data.")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    lines.append(f"| Total emails | {counts['total_emails']} |")
    lines.append(f"| Classified emails | {counts['classified_emails']} |")
    lines.append(f"| Spam-risk emails | {counts['spam_risk_emails']} |")
    lines.append(f"| Unread emails | {counts['unread_emails']} |")
    lines.append(f"| Cleanup candidates | {report['cleanup_preview']['total_candidates']} |")
    lines.append(f"| Search index warmup latency | {report['search_index']['warmup_latency_ms']} ms |")
    lines.append(f"| Inbox health latency | {report['inbox_health']['latency_ms']} ms |")
    lines.append(f"| Cleanup preview latency | {report['cleanup_preview']['latency_ms']} ms |")
    lines.append(f"| Avg search latency | {report['search']['avg_latency_ms']} ms |")
    lines.append(f"| P95 search latency | {report['search']['p95_latency_ms']} ms |")
    lines.append("")
    lines.append("## Search Latency")
    lines.append("")
    lines.append("| Query | Mode | Latency | Results | Top Subject |")
    lines.append("| --- | --- | ---: | ---: | --- |")
    for row in report["search"]["rows"]:
        top_subject = (row["top_subject"] or "").replace("|", "\\|")
        lines.append(
            f"| {row['query']} | {row['mode']} | {row['latency_ms']} ms | {row['result_count']} | {top_subject} |"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-email", default=LARGE_EMAIL)
    parser.add_argument("--seed-count", type=int, help="Seed this many synthetic emails before benchmarking")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--search-limit", type=int, default=10)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--output", default=str(Path(__file__).resolve().parents[1] / "eval" / "large_inbox_benchmark.json"))
    parser.add_argument(
        "--markdown-output",
        default=str(Path(__file__).resolve().parents[1] / "eval" / "large_inbox_benchmark.md"),
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    db = SessionLocal()
    try:
        report = run_large_inbox_benchmark(
            db,
            user_email=args.user_email,
            seed_count=args.seed_count,
            reset=args.reset,
            batch_size=args.batch_size,
            search_limit=args.search_limit,
        )
    finally:
        db.close()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    markdown_path = Path(args.markdown_output)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(report), encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(f"\nSaved JSON report to {output_path}")
    print(f"Saved Markdown report to {markdown_path}")


if __name__ == "__main__":
    main()