from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.services.classification import CATEGORIES, PRIORITIES, LLMClient, classify_fields

# The _prf_report function calculates precision, recall, and F1 score for each class label based on the true and predicted labels.
 
# It also computes overall accuracy and macro F1 score across all classes. The function returns a dictionary containing per-class metrics, overall accuracy, and macro F1 score.

def _prf_report(y_true: list[str], y_pred: list[str], labels: list[str]) -> dict[str, Any]:
    per_class: dict[str, Any] = {}
    for label in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)
        support = sum(1 for t in y_true if t == label)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        per_class[label] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "support": support,
        }

    accuracy = sum(1 for t, p in zip(y_true, y_pred) if t == p) / len(y_true) if y_true else 0.0
    represented = [m for m in per_class.values() if m["support"] > 0]
    macro_f1 = sum(m["f1"] for m in represented) / len(represented) if represented else 0.0

    return {"per_class": per_class, "accuracy": round(accuracy, 3), "macro_f1": round(macro_f1, 3)}


def evaluate_classifier(labeled_rows: list[dict[str, Any]], llm_client: LLMClient | None = None) -> dict[str, Any]:
    """Run the classification pipeline over a hand-labeled dataset and score it.

    Each row must have: sender, subject, snippet, body_preview (optional),
    label_category, label_priority, label_needs_reply.
    """
    llm_client = llm_client or LLMClient()

    y_true_category: list[str] = []
    y_pred_category: list[str] = []
    y_true_priority: list[str] = []
    y_pred_priority: list[str] = []
    y_true_reply: list[str] = []
    y_pred_reply: list[str] = []
    stage_counts: dict[str, int] = defaultdict(int)

    for row in labeled_rows:
        result = classify_fields(
            subject=row.get("subject"),
            sender=row.get("sender"),
            snippet=row.get("snippet"),
            body_preview=row.get("body_preview"),
            llm_client=llm_client,
        )
        stage_counts[result.stage] += 1

        y_true_category.append(str(row["label_category"]).strip().lower())
        y_pred_category.append(result.category)
        y_true_priority.append(str(row["label_priority"]).strip().lower())
        y_pred_priority.append(result.priority)

        label_needs_reply = str(row["label_needs_reply"]).strip().lower() in ("true", "1", "yes")
        y_true_reply.append(str(label_needs_reply))
        y_pred_reply.append(str(result.needs_reply))

    return {
        "sample_count": len(labeled_rows),
        "stage_counts": dict(stage_counts),
        "category": _prf_report(y_true_category, y_pred_category, CATEGORIES),
        "priority": _prf_report(y_true_priority, y_pred_priority, PRIORITIES),
        "needs_reply": _prf_report(y_true_reply, y_pred_reply, ["True", "False"]),
    }
