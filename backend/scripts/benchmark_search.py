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
from app.services.search import hybrid_search_emails


def reciprocal_rank(results: list[int], expected_email_id: int) -> float:
    try:
        return 1 / (results.index(expected_email_id) + 1)
    except ValueError:
        return 0.0


def hit_at_k(results: list[int], expected_email_id: int, k: int) -> float:
    return 1.0 if expected_email_id in results[:k] else 0.0


def evaluate_queries(rows: list[dict[str, str]], user: User, db) -> dict[str, Any]:
    # This benchmark is meant for Week 5/7 validation: compare how often the
    # expected email appears at the top or near the top for real user queries.
    totals = {"hit_at_1": 0.0, "hit_at_3": 0.0, "mrr": 0.0}
    details = []
    for row in rows:
        query = row["query"]
        expected_id = int(row["expected_email_id"])
        results = hybrid_search_emails(db=db, user=user, query=query, limit=10)
        result_ids = [result.email.id for result in results]
        totals["hit_at_1"] += hit_at_k(result_ids, expected_id, 1)
        totals["hit_at_3"] += hit_at_k(result_ids, expected_id, 3)
        totals["mrr"] += reciprocal_rank(result_ids, expected_id)
        details.append(
            {
                "query": query,
                "expected_email_id": expected_id,
                "top_email_id": result_ids[0] if result_ids else None,
                "hit_at_1": hit_at_k(result_ids, expected_id, 1),
                "hit_at_3": hit_at_k(result_ids, expected_id, 3),
                "rr": reciprocal_rank(result_ids, expected_id),
            }
        )

    count = len(rows) or 1
    return {
        "query_count": len(rows),
        "hit_at_1": round(totals["hit_at_1"] / count, 3),
        "hit_at_3": round(totals["hit_at_3"] / count, 3),
        "mrr": round(totals["mrr"] / count, 3),
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark MailMind hybrid email search.")
    parser.add_argument("--input", required=True, help="CSV with query,expected_email_id columns")
    parser.add_argument("--user-email", required=True, help="MailMind user email to benchmark")
    parser.add_argument("--output", default=str(Path(__file__).resolve().parents[1] / "eval" / "search_benchmark.json"))
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
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()





