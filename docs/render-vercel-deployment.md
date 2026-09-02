# Render + Vercel Deployment

This is the recommended real-user deployment path for MailMind.

## Target Setup

| Component | Platform | Why |
| --- | --- | --- |
| Backend API | Render web service | Docker support, health checks, simple logs. |
| Celery worker | Render worker service | Keeps large Gmail sync jobs outside request/response timeouts. |
| PostgreSQL | Supabase, Neon, Railway, or Render Postgres | Needs pgvector support. |
| Redis | Upstash, Railway, or Render Redis | Queue for Celery jobs. |
| Frontend | Vercel | Simple Vite static deployment. |

## 1. Backend Database

Create a hosted PostgreSQL database and confirm pgvector support.

```sql
CREATE EXTENSION IF NOT EXISTS vector;
SELECT extname FROM pg_extension WHERE extname = 'vector';
```

MailMind normalizes hosted `postgres://` and plain `postgresql://` URLs to `postgresql+psycopg://`, so provider connection strings work in production env vars.

## 2. Redis

Create Redis and copy the connection URL into all three backend queue settings:

```env
REDIS_URL=redis://...
CELERY_BROKER_URL=redis://...
CELERY_RESULT_BACKEND=redis://...
```

For TLS Redis providers, use the `rediss://` URL they provide.

## 3. Render Backend + Worker

Use `render.yaml` as the service blueprint or create services manually. The blueprint defines:

```text
mailmind-backend  -> FastAPI web API
mailmind-worker   -> Celery background worker
mailmind-redis    -> queue/result backend
```

Backend web service:

```bash
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Worker service:

```bash
celery -A app.core.celery_app.celery_app worker --loglevel=INFO
```

Health check path:

```text
/api/v1/health
```

Required backend env vars are in `.env.production.example`.

## 4. Real Gmail OAuth

In Google Cloud OAuth credentials, add:

```text
Authorized redirect URI:
https://your-render-api.onrender.com/api/v1/gmail/oauth/callback
```

Set the same value in Render:

```env
GOOGLE_REDIRECT_URI=https://your-render-api.onrender.com/api/v1/gmail/oauth/callback
GMAIL_SCOPES=openid email profile https://www.googleapis.com/auth/gmail.modify
```

Use `gmail.modify` only because MailMind supports user-confirmed archive and mark-read actions. Keep early testing limited to Google OAuth test users until the app is verified.

## 5. Optional Demo Data

After backend deploy and migrations pass, you can still seed safe demo data from the backend service shell/job:

```bash
python -m scripts.seed_demo_inbox --count 150 --reset
```

Demo login:

```text
email: demo@mailmind.dev
password: DemoPass123!
```

## 6. Vercel Frontend

Import the GitHub repo into Vercel.

Settings:

```text
Root Directory: frontend
Build Command: npm run build
Output Directory: dist
```

Environment:

```env
VITE_API_BASE_URL=https://your-render-api.onrender.com/api/v1
```

`frontend/vercel.json` includes SPA rewrites so `/cleanup` works after refresh.

## 7. Real Gmail Rollout

Start with bounded sync sizes before syncing a large inbox:

| Stage | Sync limit | Goal |
| --- | ---: | --- |
| Smoke | 25 emails | Confirm OAuth, token encryption, worker, and DB writes. |
| Small beta | 100 emails | Confirm retries, idempotent upserts, and dashboard performance. |
| Medium beta | 500 emails | Confirm search/classification cost and sync progress. |
| Large beta | 2,000+ emails | Confirm batching, user experience, and Gmail quota behavior. |

Keep `GMAIL_SYNC_QUERY=newer_than:30d` for early testing. Widen it only after smaller stages are stable.

## 8. Smoke Test

From local `backend/`, run:

```bash
python -m scripts.smoke_deployment --base-url https://your-render-api.onrender.com/api/v1 --cleanup-undo
```

Expected output starts with:

```text
MailMind deployment smoke passed
```

Real Gmail mode is healthy only when queued jobs move to `running` and then `succeeded`. If jobs stay `queued`, the worker is not running or Redis is not reachable.
