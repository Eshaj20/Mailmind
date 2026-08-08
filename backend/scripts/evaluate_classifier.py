"""Run the AI classification pipeline against a hand-labeled CSV and report
precision, recall, and F1 for category, priority, and needs_reply.

Usage (from backend/):
    python -m scripts.evaluate_classifier
    python -m scripts.evaluate_classifier --input eval/labeled_emails.csv --output eval/eval_report.md

The seed dataset at eval/labeled_emails.csv is a small synthetic set for
exercising the pipeline end to end. For a trustworthy report, replace it with
100-150 of your own real emails: run `scripts/export_emails_for_labeling.py`
to export your synced inbox to a CSV template, then hand-label the
label_category / label_priority / label_needs_reply columns yourself.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.classification import LLMClient  # noqa: E402
from app.services.evaluation import evaluate_classifier  # noqa: E402


def load_labeled_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def render_markdown(report: dict) -> str:
    lines = ["# AI Classification Evaluation Report", ""]
    lines.append(f"- Sample size: {report['sample_count']}")
    lines.append(f"- Stage usage: {report['stage_counts']}")
    lines.append("")
    for section in ("category", "priority", "needs_reply"):
        data = report[section]
        lines.append(f"## {section.replace('_', ' ').title()}")
        lines.append(f"Accuracy: {data['accuracy']}  |  Macro F1: {data['macro_f1']}")
        lines.append("")
        lines.append("| label | precision | recall | f1 | support |")
        lines.append("|---|---|---|---|---|")
        for label, metrics in data["per_class"].items():
            lines.append(
                f"| {label} | {metrics['precision']} | {metrics['recall']} | {metrics['f1']} | {metrics['support']} |"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="eval/labeled_emails.csv", help="Path to labeled CSV")
    parser.add_argument("--output", default="eval/eval_report.md", help="Where to write the markdown report")
    args = parser.parse_args()

    rows = load_labeled_csv(Path(args.input))
    if not rows:
        raise SystemExit(f"No rows found in {args.input}")

    report = evaluate_classifier(rows, llm_client=LLMClient())
    markdown = render_markdown(report)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")

    print(markdown)
    print(f"\nSaved report to {output_path}")


if __name__ == "__main__":
    main()
