# Self-Hosted MailMind

This setup runs MailMind entirely on one computer with Docker. It does not use
Vercel, Cloudflare Tunnel, or a public backend URL. The web app is available at
`http://localhost:8080` while Docker is running.

## What This Is And Is Not

- It is a real local multi-service installation: frontend, API, Celery worker,
  Redis, PostgreSQL, and persisted Docker volumes.
- It is not a centrally hosted SaaS. Each person who uses it runs their own
  installation and connects their own Gmail account.
- The Gmail OAuth callback is local, so it remains stable and does not change
  after a restart.

## First Launch

1. Install Docker Desktop and start it.
2. Copy `.env.selfhosted.example` to `.env.selfhosted`.
3. Generate values for `POSTGRES_PASSWORD` and `SECRET_KEY`. The password in
   `DATABASE_URL` must exactly match `POSTGRES_PASSWORD`.
4. In Google Cloud, create an OAuth web client and add this authorized redirect
   URI exactly:

   ```text
   http://localhost:8000/api/v1/gmail/oauth/callback
   ```

5. Put that client ID and secret into `.env.selfhosted`.
6. Start MailMind:

   ```powershell
   docker compose -f docker-compose.selfhosted.yml --env-file .env.selfhosted up --build -d
   ```

7. Open `http://localhost:8080`, create an account, and connect Gmail.

## Normal Operations

```powershell
# Check services
docker compose -f docker-compose.selfhosted.yml --env-file .env.selfhosted ps

# Follow logs
docker compose -f docker-compose.selfhosted.yml --env-file .env.selfhosted logs -f backend worker

# Stop without deleting inbox data
docker compose -f docker-compose.selfhosted.yml --env-file .env.selfhosted down
```

Do not run `down -v` unless you intentionally want to erase the local database
and Redis volumes.

## Gmail Privacy And OAuth

Google does not receive a user's MailMind password. Gmail access is granted by
that user's Google consent screen and can be revoked in their Google Account.
MailMind stores the Gmail refresh token encrypted in its local PostgreSQL
database. Never share `.env.selfhosted`, Docker volumes, OAuth client secrets,
or SMTP app passwords.

For more than your own test users, configure the OAuth consent screen correctly
and complete Google's verification requirements for the requested Gmail scope.
