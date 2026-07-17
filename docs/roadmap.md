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
- Structured logging

## Week 4: AI Layer

Classify emails, score priority, detect whether they need a reply, and summarize threads.

Deliverables:

- Stored AI metadata
- Dashboard that shows meaningful email intelligence

## Week 5: Semantic Search

Install pgvector, generate embeddings, and let users search email by meaning.

Deliverables:

- Email embeddings
- Query embeddings
- Similarity search endpoint and UI

## Week 6: Inbox Intelligence

Add higher-level assistant features.

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

## Week 8: Polish

Make the project portfolio-ready.

Deliverables:

- Dashboard polish and charts
- Architecture, sequence, and ER diagrams
- Screenshots and demo video
- Deployment guide
