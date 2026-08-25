# Classification evaluation set

`labeled_emails.csv` is a **40-row synthetic seed set** covering all five
categories, all three priorities, and both `needs_reply` values. It exists so
the evaluation harness (`scripts/evaluate_classifier.py`) runs out of the box
and CI can catch regressions in the rule engine.

It is **not** the "100-150 hand-labeled real emails" called for in the Week 4
plan - synthetic examples make the pipeline easy to demo but don't tell you
how the classifier performs on your actual inbox's noise, slang, and edge
cases.

To build a real evaluation set:

1. Sync your inbox (Week 2/3 features already do this).
2. Run `python -m scripts.export_emails_for_labeling --email you@example.com --limit 150`
   from `backend/` to export your synced emails to a CSV template.
3. Hand-label 100-150 rows: fill in `label_category`, `label_priority`, and
   `label_needs_reply`.
4. Run `python -m scripts.evaluate_classifier --input eval/labeled_emails.csv`
   to get a precision/recall/F1 report in `eval/eval_report.md`.

Re-run step 4 whenever you change the rule engine, keyword lists, or model
version to track whether accuracy improved or regressed.

