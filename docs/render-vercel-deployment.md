# Render + Vercel Deployment

This is the recommended portfolio deployment path for MailMind.

## Target Setup

| Component | Platform | Why |
| --- | --- | --- |
| Backend API | Render web service | Docker support, health checks, simple logs. |
| Celery worker | Render worker service | Same backend image, separate worker command. |
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

## 3. Render Backend

Use `render.yaml` as the service blueprint or create services manually.

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

## 3. Seed Demo Data

After backend deploy and migrations pass, run this from the Render shell/job for the backend service:

```bash
python -m scripts.seed_demo_inbox --count 150 --reset
```

Demo login:

```text
email: demo@mailmind.dev
password: DemoPass123!
```

## 4. Vercel Frontend

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

## 5. Smoke Test

From local `backend/`, run:

```bash
python -m scripts.smoke_deployment --base-url https://your-render-api.onrender.com/api/v1 --cleanup-undo
```

Expected output starts with:

```text
MailMind deployment smoke passed
```

## 6. Real Gmail Background Sync Later

For demo-only portfolio deployment, Gmail OAuth, Redis, and Celery worker can stay disabled. The demo inbox works without Google credentials or background sync.

When enabling real Gmail background sync, add Redis and a worker service with this command:

```bash
celery -A app.core.celery_app.celery_app worker --loglevel=INFO
```

Then set:

```env
GOOGLE_REDIRECT_URI=https://your-render-api.onrender.com/api/v1/gmail/oauth/callback
CORS_ORIGINS=https://your-vercel-app.vercel.app
```

Add the same callback URL in Google Cloud OAuth credentials.