# Deployment Guide

MailMind deploys as five services:

- `backend`: FastAPI API server
- `frontend`: React/Vite static frontend
- `worker`: Celery worker for Gmail sync and async jobs
- `postgres`: PostgreSQL with pgvector enabled
- `redis`: Celery broker/result backend

## Recommended Portfolio Deployment

For the fastest recruiter-ready deployment, use:

| Layer | Recommended Option | Notes |
| --- | --- | --- |
| Frontend | Vercel or Netlify | Static Vite build. |
| Backend | Render, Railway, or Fly.io | Runs FastAPI with the backend Dockerfile. |
| Worker | Same backend platform as a worker service | Same image/env, different start command. |
| PostgreSQL | Supabase, Neon, Render Postgres, or Railway Postgres | Must support `CREATE EXTENSION vector`. |
| Redis | Upstash, Render Redis, or Railway Redis | Used by Celery queue. |

## Backend Environment

Use `.env.production.example` as the backend template.

Required:

```env
ENVIRONMENT=production
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME
SECRET_KEY=replace-with-random-32-plus-character-secret
CORS_ORIGINS=https://your-frontend-domain.example
REDIS_URL=redis://USER:PASSWORD@HOST:6379/0
CELERY_BROKER_URL=redis://USER:PASSWORD@HOST:6379/0
CELERY_RESULT_BACKEND=redis://USER:PASSWORD@HOST:6379/1
```

Gmail OAuth, only if real Gmail connection is enabled:

```env
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=https://your-api-domain.example/api/v1/gmail/oauth/callback
GMAIL_SCOPES=openid email profile https://www.googleapis.com/auth/gmail.modify
```

OpenAI is optional because the local fallback classifier works without it:

```env
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```

## Frontend Environment

Create the frontend env from `frontend/.env.example`:

```env
VITE_API_BASE_URL=https://your-api-domain.example/api/v1
```

## Service Commands

Backend web service:

```bash
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Celery worker service:

```bash
celery -A app.core.celery_app.celery_app worker --loglevel=INFO
```

Frontend build:

```bash
npm ci
npm run build
```

Frontend publish directory:

```text
dist
```

## Database Setup

Run migrations after PostgreSQL is provisioned:

```bash
cd backend
alembic upgrade head
```

Confirm pgvector exists:

```sql
SELECT extname FROM pg_extension WHERE extname = 'vector';
```

The Week 5 migration creates the `vector` extension automatically on Postgres.

## Demo Data Setup

For a deployed portfolio demo, seed synthetic data instead of exposing private Gmail:

```bash
python -m scripts.seed_demo_inbox --count 150 --reset
```

Demo login:

```text
email: demo@mailmind.dev
password: DemoPass123!
```

For benchmark proof, run:

```bash
python -m scripts.benchmark_large_inbox --seed-count 10000 --reset --batch-size 500
```

This creates aggregate outputs in `backend/eval/large_inbox_benchmark.md` and `.json`.

## Google OAuth Production Setup

If enabling real Gmail:

1. Set the OAuth redirect URI to `https://your-api-domain.example/api/v1/gmail/oauth/callback`.
2. Add your deployed frontend domain to authorized JavaScript origins if Google asks for it.
3. Keep test users limited while the app is unverified.
4. Keep cleanup review-first; never auto-delete emails.
5. Use `gmail.modify` only because archive/mark-read actions update Gmail labels.

## Smoke Checks

Backend health:

```bash
curl https://your-api-domain.example/api/v1/healthz
curl https://your-api-domain.example/api/v1/health
```

Frontend flow:

1. Open the frontend deployment.
2. Click `Use demo workspace` on the auth page.
3. Login.
4. Confirm dashboard loads demo emails, inbox health, cleanup preview, search, and sender insights.
5. Open `/cleanup`, apply archive/mark-read to demo emails, then undo.

API smoke after login:

```bash
curl https://your-api-domain.example/api/v1/gmail/accounts \
  -H "Authorization: Bearer <jwt>"

curl https://your-api-domain.example/api/v1/gmail/cleanup/preview \
  -H "Authorization: Bearer <jwt>"

curl "https://your-api-domain.example/api/v1/gmail/search?q=electricity%20bill" \
  -H "Authorization: Bearer <jwt>"
```

## Automated Smoke Test

After seeding the demo inbox, run the smoke script against local or deployed API:

```bash
python -m scripts.smoke_deployment --base-url https://your-api-domain.example/api/v1
```

For a reversible cleanup action check on demo data:

```bash
python -m scripts.smoke_deployment --base-url https://your-api-domain.example/api/v1 --cleanup-undo
```

## Deployment Checklist

- [ ] Backend env vars configured from `.env.production.example`.
- [ ] Frontend `VITE_API_BASE_URL` points to deployed backend `/api/v1`.
- [ ] PostgreSQL supports pgvector.
- [ ] Redis URL works from both backend and worker.
- [ ] `alembic upgrade head` succeeds.
- [ ] Backend health returns `{"status":"ok"}`.
- [ ] Demo inbox seeded on deployed DB.
- [ ] Auth page demo login works.
- [ ] Dashboard loads inbox health, search, cleanup preview, and sender intelligence.
- [ ] `python -m scripts.smoke_deployment --base-url <api>/api/v1` passes.
- [ ] Cleanup action and undo work in demo mode.
- [ ] Google OAuth redirect URI updated if real Gmail is enabled.
- [ ] README has deployed frontend URL, backend URL, screenshots, and benchmark table.

## Production Notes

- Keep Gmail cleanup review-first; do not auto-delete emails.
- Move the in-process rate limiter to Redis if multiple backend replicas are deployed.
- Run worker and API from the same release image so models/schemas stay aligned.
- Use aggregate benchmark numbers publicly; keep real Gmail exports under `backend/eval/private/`.