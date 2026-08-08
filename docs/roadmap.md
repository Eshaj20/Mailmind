# Eight-Week Build Roadmap

## Week 1: Foundation

Ship a working auth-backed app with Docker, FastAPI, PostgreSQL, React, and tests.

Deliverables:

- User signup
- Login
- Database connection
- Docker Compose stack

## Week 2: Gmail Integration

Implement Google OAuth, store refresh tokens, and sync the latest emails into PostgreSQL.

Deliverables:

- Gmail account connection
- First inbox sync
- Users, threads, and emails tables

## Week 3: Production Sync Engine

Replace full fetches with Gmail `historyId` incremental sync and move long-running tasks into Redis/Celery workers.

Deliverables:

- Redis/Celery async worker process
- Sync job status tracking for queued, running, retrying, succeeded, and failed states
- Retry mechanism for temporary Google API failures
- Incremental sync using Gmail history IDs
- Idempotent re-sync with no duplicate rows on re-run
- Structured logging

## Week 4: AI Layer - Done

Hand-label 100-150 real emails, then classify, score priority, detect whether they need a reply, and summarize threads.

Deliverables:

- Labeled evaluation set - `scripts/export_emails_for_labeling.py` exports synced emails to a CSV template; `eval/labeled_emails.csv` ships a 40-row synthetic seed so the harness runs out of the box (swap in 100-150 real hand-labeled emails for a trustworthy report; see `eval/README.md`)
- Two-stage classification: rule-based pre-filter (`app/services/classification.py::apply_rule_engine`), then LLM (OpenAI, if `OPENAI_API_KEY` is set) or a lightweight local fallback for the rest
- Classification logs with confidence and model_version - append-only `email_classifications` table
- Precision, recall, and F1 report on the labeled set - `scripts/evaluate_classifier.py` writes `eval/eval_report.md`
- Stored AI metadata - `category`, `priority`, `needs_reply`, `classification_confidence`, `classification_model_version`, `classified_at` on `Email`; `summary` on `EmailThread`
- Dashboard that shows meaningful email intelligence - category/priority breakdown, needs-reply count, thread summaries, and a "Run AI classification" action

## Week 5: Semantic Search

Install pgvector, generate embeddings, and build hybrid search with Postgres full-text search plus pgvector, merged with Reciprocal Rank Fusion.

Deliverables:

- Email embeddings
- Query embeddings
- Hybrid full-text + vector ranking with RRF
- Benchmark hybrid search vs. vector-only vs. keyword-only
- Similarity search endpoint and UI

## Week 6: Inbox Intelligence

Add higher-level assistant features with a defined health score formula: unread ratio + average response time + still-mailing-after-unsubscribe count.

Deliverables:

- Inbox health score
- Follow-up detection
- Newsletter cleanup suggestions
- Weekly report

## Week 7: Production Engineering

Harden the system for public demo use.

Deliverables:

- Unit and integration tests
- Rate limiting
- Pagination, filtering, and sorting
- API docs cleanup
- Basic monitoring
- Cost and token usage tracking per user

## Week 8: Polish

Make the project portfolio-ready.

Deliverables:

- Dashboard polish and charts
- Architecture, sequence, and ER diagrams
- Evaluation numbers and benchmark table in the README
- Screenshots and demo video
- Deployment guide


