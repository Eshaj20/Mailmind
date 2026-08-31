# Spam Detection And Public Dataset Evaluation

MailMind supports spam-risk scoring without using private Gmail data for training.

## Design

The spam layer has two modes:

1. Optional pretrained local model: set `SPAM_MODEL_PATH` to a `.joblib` model that supports `predict_proba` or `predict`.
2. Deterministic heuristic fallback: used automatically when no model file is configured, so Docker, tests, and demo mode work offline.

Each classified email stores:

- `spam_label`
- `spam_score`
- `spam_model_version`
- `spam_detected_at`

High-risk spam can override the main email category to `spam`, while medium-risk spam still improves cleanup ranking.

## Why This Approach

Personal Gmail labeling is expensive and risky from a privacy point of view. Public spam/ham corpora such as Enron or TREC are better for repeatable evaluation, while real Gmail can remain an optional product smoke test.

## Public Dataset Workflow

Download a public CSV separately, then run from `backend/`:

```bash
python -m scripts.evaluate_spam_detector --input path/to/spam_dataset.csv --output eval/spam_eval_report.md
```

Supported CSV shapes:

```text
text,label
```

or:

```text
subject,sender,snippet,body_preview,label
```

Accepted labels include `spam`, `ham`, `1`, `0`, `true`, and `false`.

## Model Notes

A lightweight Hugging Face/sklearn-style spam model can be downloaded manually and configured locally:

```env
SPAM_MODEL_PATH=models/spam_model.joblib
SPAM_MODEL_VERSION=enron-spam-logreg-v1
```

The application does not download models at runtime. That keeps production startup predictable and avoids requiring a paid API key for spam scoring.