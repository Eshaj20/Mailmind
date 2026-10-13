# MailMind

MailMind is an AI-assisted Gmail inbox manager. It connects a user-owned Gmail
account, syncs messages in the background, classifies and searches the inbox,
and suggests safe cleanup actions for user review. It does not automatically
delete email.

## Proof Of Work

- **Frontend:** React, TypeScript, React Query, responsive dashboard and cleanup review.
- **Backend:** FastAPI, Pydantic validation, JWT authentication, SQLAlchemy and Alembic.
- **Data:** PostgreSQL + pgvector, idempotent Gmail persistence, full-text search.
- **Background jobs:** Redis and Celery for non-blocking Gmail sync and retries.
- **AI:** deterministic rules for obvious messages, structured LLM classification when configured, and a local fallback when it is unavailable.
- **Search:** PostgreSQL full-text + vector similarity, merged with Reciprocal Rank Fusion (RRF).

## Architecture

```text
React frontend -> FastAPI API -> PostgreSQL + Redis
                                  |
                              Celery worker -> Gmail API / optional LLM
```

### Reliability Decisions

- Gmail sync jobs have explicit queued, running, retrying, succeeded, and failed states.
- `historyId` fetches incremental Gmail changes after the first sync.
- `UNIQUE(gmail_account_id, gmail_message_id)` plus upsert makes repeated syncs idempotent.
- Cleanup actions require explicit user review and have audit/undo support.

## Run Locally

### Developer Setup

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Open `http://localhost:5173`. API docs are at `http://localhost:8000/docs`.

### Self-Hosted Setup

For a stable no-card installation on one computer, follow the
[self-hosted guide](docs/self-hosted.md). It starts the whole stack at
`http://localhost:8080` without Vercel or a Cloudflare Tunnel.

```powershell
Copy-Item .env.selfhosted.example .env.selfhosted
docker compose -f docker-compose.selfhosted.yml --env-file .env.selfhosted up --build -d
```

Each installation owns its Gmail credentials and local database. This is
self-hosted software, not a centrally hosted public SaaS.

## Verification

```powershell
# Backend tests
cd backend
pytest

# Frontend type-check and build
cd ../frontend
npm install
npm run lint
npm run build
```

The Gmail sync test suite verifies that a 500-message initial sync creates 500
records and a repeat sync creates no duplicates.

## Documentation

- [Architecture](docs/architecture.md)
- [API reference](docs/api.md)
- [Deployment guide](docs/deployment.md)
- [Self-hosted installation](docs/self-hosted.md)
- [Search benchmark](docs/search-benchmark.md)

