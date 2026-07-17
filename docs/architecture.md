# Architecture

## System Context

MailMind is split into a React client, FastAPI backend, PostgreSQL database, Redis broker, and background workers. The backend owns authentication, API contracts, Gmail OAuth, and user-facing queries. Workers own long-running sync and AI jobs.

```mermaid
sequenceDiagram
  participant User
  participant React
  participant FastAPI
  participant Postgres
  participant Redis
  participant Worker
  participant Gmail

  User->>React: Login
  React->>FastAPI: POST /auth/login
  FastAPI->>Postgres: Verify user
  FastAPI-->>React: JWT
  User->>React: Connect Gmail
  React->>FastAPI: Start OAuth
  FastAPI-->>React: Google consent URL
  Gmail-->>FastAPI: OAuth callback
  FastAPI->>Postgres: Store encrypted refresh token
  FastAPI->>Redis: Queue initial sync
  Worker->>Gmail: Fetch messages
  Worker->>Postgres: Store threads and emails
```

## Initial Data Model

```mermaid
erDiagram
  USERS ||--o{ GMAIL_ACCOUNTS : owns
  USERS ||--o{ THREADS : owns
  THREADS ||--o{ EMAILS : contains

  USERS {
    int id PK
    string email
    string full_name
    string hashed_password
    datetime created_at
  }

  GMAIL_ACCOUNTS {
    int id PK
    int user_id FK
    string google_email
    string refresh_token_ciphertext
    string history_id
  }

  THREADS {
    int id PK
    int user_id FK
    string gmail_thread_id
    string subject
  }

  EMAILS {
    int id PK
    int thread_id FK
    string gmail_message_id
    string sender
    string snippet
    datetime received_at
  }
```

## Production Notes

- Encrypt OAuth refresh tokens before writing them to PostgreSQL.
- Use Gmail `historyId` for incremental sync after the initial import.
- Move sync, embeddings, summaries, and classification into workers.
- Add idempotency keys around Gmail message imports.
- Add pagination and filtering before syncing large accounts.
