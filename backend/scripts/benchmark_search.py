from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.gmail import Email
from app.models.user import User
from app.services.search import search_emails_by_mode

SEARCH_MODES = ("keyword", "vector", "hybrid")


def reciprocal_rank(results: list[int], expected_email_id: int) -> float:
    try:
        return 1 / (results.index(expected_email_id) + 1)
    except ValueError:
        return 0.0


def hit_at_k(results: list[int], expected_email_id: int, k: int) -> float:
    return 1.0 if expected_email_id in results[:k] else 0.0


def _empty_totals() -> dict[str, float]:
    return {"hit_at_1": 0.0, "hit_at_3": 0.0, "mrr": 0.0}


def _score_result_ids(result_ids: list[int], expected_email_id: int) -> dict[str, float | int | None]:
    return {
        "top_email_id": result_ids[0] if result_ids else None,
        "hit_at_1": hit_at_k(result_ids, expected_email_id, 1),
        "hit_at_3": hit_at_k(result_ids, expected_email_id, 3),
        "rr": reciprocal_rank(result_ids, expected_email_id),
    }


def evaluate_queries(rows: list[dict[str, str]], user: User, db) -> dict[str, Any]:
    """Compare keyword-only, vector-only, and hybrid RRF retrieval.

    Each CSV row represents one labeled search query and the email that should
    appear in the result set. The output is intentionally small enough to paste
    into README tables while still keeping per-query details for debugging.
    """
    totals = {mode: _empty_totals() for mode in SEARCH_MODES}
    details = []

    for row in rows:
        query = row["query"]
        expected_id = int(row["expected_email_id"])
        detail: dict[str, Any] = {"query": query, "expected_email_id": expected_id}

        for mode in SEARCH_MODES:
            results = search_emails_by_mode(db=db, user=user, query=query, limit=10, mode=mode)
            result_ids = [result.email.id for result in results]
            scores = _score_result_ids(result_ids, expected_id)
            totals[mode]["hit_at_1"] += float(scores["hit_at_1"])
            totals[mode]["hit_at_3"] += float(scores["hit_at_3"])
            totals[mode]["mrr"] += float(scores["rr"])
            detail[mode] = scores

        details.append(detail)

    count = len(rows) or 1
    modes = {
        mode: {
            "hit_at_1": round(totals[mode]["hit_at_1"] / count, 3),
            "hit_at_3": round(totals[mode]["hit_at_3"] / count, 3),
            "mrr": round(totals[mode]["mrr"] / count, 3),
        }
        for mode in SEARCH_MODES
    }
    best_mode = max(SEARCH_MODES, key=lambda mode: (modes[mode]["mrr"], modes[mode]["hit_at_3"], modes[mode]["hit_at_1"]))

    return {
        "query_count": len(rows),
        "modes": modes,
        "best_mode": best_mode,
        "details": details,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Search Benchmark Report", ""]
    lines.append(f"- Query count: {report['query_count']}")
    lines.append(f"- Best mode by MRR: {report['best_mode']}")
    lines.append("")
    lines.append("| Mode | Hit@1 | Hit@3 | MRR |")
    lines.append("| --- | ---: | ---: | ---: |")
    for mode in SEARCH_MODES:
        metrics = report["modes"][mode]
        lines.append(f"| {mode} | {metrics['hit_at_1']} | {metrics['hit_at_3']} | {metrics['mrr']} |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark MailMind email search modes.")
    parser.add_argument("--input", required=True, help="CSV with query,expected_email_id columns")
    parser.add_argument("--user-email", required=True, help="MailMind user email to benchmark")
    parser.add_argument("--output", default=str(Path(__file__).resolve().parents[1] / "eval" / "search_benchmark.json"))
    parser.add_argument("--markdown-output", default=str(Path(__file__).resolve().parents[1] / "eval" / "search_benchmark.md"))
    args = parser.parse_args()

    rows = list(csv.DictReader(Path(args.input).open(newline="", encoding="utf-8")))
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == args.user_email))
        if user is None:
            raise SystemExit(f"User not found: {args.user_email}")
        missing = [row["expected_email_id"] for row in rows if db.get(Email, int(row["expected_email_id"])) is None]
        if missing:
            raise SystemExit(f"Expected email IDs not found: {', '.join(missing)}")
        report = evaluate_queries(rows, user, db)
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
