# Deployment Guide

MailMind is designed as five deployable services:

- `backend`: FastAPI API server
- `frontend`: React/Vite static frontend
- `worker`: Celery Gmail sync worker
- `postgres`: PostgreSQL with pgvector enabled
- `redis`: queue/broker for background jobs

## Required Environment

Backend:

```env
DATABASE_URL=postgresql+psycopg://...
SECRET_KEY=replace-with-production-secret
CORS_ORIGINS=https://your-frontend-domain
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=https://your-api-domain/api/v1/gmail/oauth/callback
GMAIL_SCOPES=openid email profile https://www.googleapis.com/auth/gmail.modify
REDIS_URL=redis://...
CELERY_BROKER_URL=redis://...
CELERY_RESULT_BACKEND=redis://...
OPENAI_API_KEY=...
OPENAI_INPUT_COST_PER_1M_TOKENS=0.0
OPENAI_OUTPUT_COST_PER_1M_TOKENS=0.0
API_RATE_LIMIT_PER_MINUTE=120
```

Frontend:

```env
VITE_API_BASE_URL=https://your-api-domain/api/v1
```

## Release Flow

1. Build backend and frontend images.
2. Run Alembic migrations against Postgres.
3. Start FastAPI API service.
4. Start Redis.
5. Start Celery worker with the same backend image/env.
6. Deploy frontend static build.
7. Update Google OAuth redirect URI to the production backend callback.

## Smoke Checks

```bash
curl https://your-api-domain/api/v1/health
```

After login and Gmail connection, verify:

- `GET /api/v1/gmail/accounts`
- `POST /api/v1/gmail/sync`
- `GET /api/v1/gmail/sync/health`
- `POST /api/v1/gmail/classify`
- `GET /api/v1/gmail/ai/usage`

## Production Notes

- Keep Gmail cleanup review-first; do not auto-delete emails.
- Use `gmail.modify` only when archive/mark-read actions are enabled.
- Move the in-process rate limiter to Redis if multiple backend replicas are deployed.
- Run worker and API from the same release image so models/schemas stay aligned.