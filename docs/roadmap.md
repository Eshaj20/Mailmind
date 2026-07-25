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

- Async worker process
- Retry mechanism
- Idempotent re-sync with no duplicate rows on re-run
- Structured logging

## Week 4: AI Layer

Hand-label 100-150 real emails, then classify, score priority, detect whether they need a reply, and summarize threads.

Deliverables:

- Labeled evaluation set
- Two-stage classification: rule-based pre-filter, then LLM/lightweight classifier for the rest
- Classification logs with confidence and model_version
- Precision, recall, and F1 report on the labeled set
- Stored AI metadata
- Dashboard that shows meaningful email intelligence

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
