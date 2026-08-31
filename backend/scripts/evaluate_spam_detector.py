"""Evaluate MailMind spam detection on a public spam/ham CSV.

Expected CSV columns can be either:
- text,label
- email,label
- subject,snippet,body_preview,label

Labels should be spam/ham, 1/0, true/false, or junk/nonspam-like values.
This script intentionally avoids downloading datasets at runtime; download public
Enron/TREC/Hugging Face data separately, then point --input at the CSV.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable

from app.services.spam_detection import detect_spam_fields

DEFAULT_OUTPUT = Path("eval/spam_eval_report.md")


def _normalise_label(value: str) -> str:
    cleaned = value.strip().lower()
    if cleaned in {"1", "true", "spam", "junk", "phishing", "bad"}:
        return "spam"
    return "ham"


def _row_text(row: dict[str, str]) -> tuple[str | None, str | None, str | None, str | None]:
    if row.get("text") or row.get("email") or row.get("message"):
        return None, row.get("sender"), row.get("text") or row.get("email") or row.get("message"), None
    return row.get("subject"), row.get("sender"), row.get("snippet"), row.get("body_preview") or row.get("body")


def evaluate_rows(rows: Iterable[dict[str, str]]) -> dict[str, float | int]:
    tp = fp = tn = fn = total = 0
    for row in rows:
        expected = _normalise_label(row.get("label") or row.get("Label") or row.get("target") or row.get("spam") or "ham")
        subject, sender, snippet, body_preview = _row_text(row)
        predicted = detect_spam_fields(subject, sender, snippet, body_preview).label
        total += 1
        if expected == "spam" and predicted == "spam":
            tp += 1
        elif expected == "ham" and predicted == "spam":
            fp += 1
        elif expected == "ham" and predicted == "ham":
            tn += 1
        else:
            fn += 1

    accuracy = (tp + tn) / total if total else 0.0
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "sample_count": total,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
    }


def write_report(metrics: dict[str, float | int], output_path: Path, source_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Spam Detection Evaluation",
        "",
        f"Source CSV: `{source_path}`",
        f"Sample size: {metrics['sample_count']}",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Accuracy | {metrics['accuracy']} |",
        f"| Precision | {metrics['precision']} |",
        f"| Recall | {metrics['recall']} |",
        f"| F1 | {metrics['f1']} |",
        "",
        "| Confusion Matrix Cell | Count |",
        "| --- | ---: |",
        f"| True positive | {metrics['true_positive']} |",
        f"| False positive | {metrics['false_positive']} |",
        f"| True negative | {metrics['true_negative']} |",
        f"| False negative | {metrics['false_negative']} |",
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Path to public spam/ham CSV")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Markdown report output path")
    args = parser.parse_args()

    input_path = Path(args.input)
    with input_path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        rows = list(csv.DictReader(handle))

    metrics = evaluate_rows(rows)
    write_report(metrics, Path(args.output), input_path)
    print(f"Evaluated {metrics['sample_count']} rows")
    print(f"Accuracy={metrics['accuracy']} Precision={metrics['precision']} Recall={metrics['recall']} F1={metrics['f1']}")
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()