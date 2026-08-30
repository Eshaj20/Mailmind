# MailMind System Design

MailMind is an AI-powered Gmail cleaner and inbox intelligence SaaS. It connects a user's Gmail account, syncs emails in the background, classifies messages, ranks search results with hybrid retrieval, and suggests safe cleanup actions.

## 1. Problem Statement

Normal inboxes become noisy because newsletters, promotions, alerts, bills, recruiter emails, and pending replies all sit in the same place. MailMind solves this by adding reliable Gmail ingestion, AI classification, hybrid search, inbox health scoring, and review-first cleanup actions.

## 2. Requirements

Functional requirements:

- Users can sign up, log in, and access protected APIs.
- Users can connect Gmail through Google OAuth.
- The backend can fetch and store Gmail emails and threads.
- Re-sync should not create duplicate email rows.
- Sync should run in the background, not block API requests.
- Emails can be classified by category, priority, and reply need.
- Users can search emails using hybrid keyword + semantic search.
- Users can preview cleanup candidates before applying Gmail changes.
- Users can give feedback when AI labels are wrong.

Non-functional requirements:

- Reliability for retries, timeouts, and partial Gmail failures.
- Security for passwords, JWTs, OAuth state, and refresh tokens.
- Observability through sync states, error counts, and AI usage logs.
- Testability with deterministic local fallbacks for AI/search.
- Deployability with Dockerized backend, frontend, worker, Redis, and PostgreSQL.

## 3. High-Level Architecture

```mermaid
flowchart LR
    User[User] --> Frontend[React + TypeScript]
    Frontend --> API[FastAPI API]

    API --> Postgres[(PostgreSQL)]
    API --> Redis[(Redis Queue)]
    Redis --> Worker[Celery Worker]

    API --> GoogleOAuth[Google OAuth]
    GoogleOAuth --> GmailAPI[Gmail API]
    Worker --> GmailAPI

    Worker --> Postgres
    API --> Classifier[Rule-Based + LLM Classifier]
    Classifier --> Postgres

    API --> Search[Full-Text + pgvector + RRF]
    Search --> Postgres

    API --> Cleanup[Gmail Cleanup Actions]
    Cleanup --> GmailAPI
    Cleanup --> Postgres
```

Interview explanation:

> MailMind has five major flows: auth, Gmail OAuth, background sync, AI classification, and inbox intelligence. FastAPI handles APIs, PostgreSQL stores users/emails/jobs/AI metadata, Redis and Celery run long Gmail sync jobs asynchronously, and the frontend consumes protected APIs using JWT authentication.

## 4. Auth And JWT Flow

```mermaid
sequenceDiagram
    participant U as User
    participant FE as React Frontend
    participant API as FastAPI
    participant DB as PostgreSQL

    U->>FE: Sign up / log in
    FE->>API: POST /auth/signup or /auth/login
    API->>API: Hash or verify password
    API->>DB: Read/write user
    API-->>FE: JWT access token
    FE->>API: Protected request with Bearer token
    API->>API: Decode JWT and load current user
```

Design decision:

- JWT keeps the backend stateless for authenticated API calls.
- Passwords are hashed before storage, so plaintext passwords are never stored.
- The current-user dependency centralizes auth checks so routes do not repeat token parsing logic.

## 5. Gmail OAuth Flow

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as FastAPI
    participant Google as Google OAuth
    participant DB as PostgreSQL

    FE->>API: GET /gmail/oauth/authorize
    API-->>FE: Google consent URL with state
    FE->>Google: User grants consent
    Google->>API: Redirect with code + state
    API->>API: Validate state
    API->>Google: Exchange code for tokens
    API->>Google: Fetch Gmail profile
    API->>DB: Store account + encrypted refresh token
    API->>Google: Fetch initial emails
    API->>DB: Upsert emails and threads
```

Design decision:

- OAuth state prevents callback misuse and ties the callback to the MailMind user.
- Refresh tokens are encrypted before persistence because they can be used to access Gmail later.
- The callback does a small first sync so the dashboard has data immediately after connection.

## 6. Async Sync And Idempotency

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as FastAPI
    participant Redis as Redis
    participant Worker as Celery Worker
    participant Gmail as Gmail API
    participant DB as PostgreSQL

    FE->>API: POST /gmail/sync
    API->>DB: Create sync_job(status=queued)
    API->>Redis: Enqueue job id
    API-->>FE: 202 Accepted + job details
    Redis->>Worker: Deliver job
    Worker->>DB: status=running
    Worker->>Gmail: Fetch changes using historyId
    Gmail-->>Worker: Messages / changes
    Worker->>DB: Upsert by Gmail message id
    Worker->>DB: Update historyId + status=succeeded
```

Design decision:

- Gmail sync is slow and can fail, so it runs in Celery instead of blocking the HTTP request.
- Redis acts as the broker between FastAPI and workers.
- `historyId` supports incremental sync, so the app fetches new changes instead of repeatedly fetching everything.
- Idempotent upsert and unique message identity make retries safe. If the same Gmail message is fetched twice, the existing row is updated instead of duplicated.

Failure handling:

- Temporary Gmail failures move jobs into retrying states.
- Permanent failures move jobs to failed with error type/message.
- `/gmail/sync/health` summarizes queued, running, retrying, succeeded, and failed jobs for observability.

## 7. AI Classification Flow

```mermaid
flowchart TD
    Email[Email] --> Rules[Rule-Based Pre-Filter]
    Rules -->|Obvious newsletter/promo/bill| LocalLabel[Deterministic Label]
    Rules -->|Ambiguous email| LLM[LLM or Lightweight Fallback]
    LLM --> Label[Category + Priority + Needs Reply]
    LocalLabel --> Label
    Label --> Snapshot[Latest Email AI Fields]
    Label --> Audit[Append-Only Classification Log]
    Label --> Usage[AI Usage / Cost Ledger]
```

Design decision:

- Two-stage classification controls cost and latency.
- Rule-based classification handles obvious emails without needing an LLM call.
- LLM or local fallback handles ambiguous emails where language understanding matters.
- `confidence` and `model_version` are stored so future evaluation can compare behavior across classifier versions.
- The latest label is stored on the email row for fast dashboard reads, while logs keep history for audit/evaluation.

## 8. Hybrid Search Flow

```mermaid
flowchart LR
    Query[User Query] --> Keyword[PostgreSQL Full-Text Search]
    Query --> Embed[Query Embedding]
    Embed --> Vector[pgvector Cosine Search]
    Keyword --> RRF[Reciprocal Rank Fusion]
    Vector --> RRF
    RRF --> Results[Ranked Email Results]
```

Design decision:

- Keyword search is strong for exact strings like names, invoice numbers, company names, and dates.
- Vector search is strong for vague intent like "interview follow up" or "electricity bill".
- RRF merges both ranked lists without needing scores to be on the same scale.
- Deterministic local embeddings keep tests offline and predictable, while pgvector keeps the production design ready for real embeddings.

## 9. Inbox Intelligence And Cleanup

```mermaid
flowchart TD
    Emails[Synced + Classified Emails] --> Health[Inbox Health Score]
    Emails --> Preview[Cleanup Preview]
    Emails --> Senders[Sender Intelligence]
    Health --> Dashboard[Dashboard]
    Preview --> Dashboard
    Senders --> Dashboard
    Dashboard --> Confirm[User Confirms Action]
    Confirm --> GmailModify[Gmail Modify API]
    GmailModify --> LocalMirror[Mirror Labels Locally]
```

Design decision:

- Cleanup is review-first because email deletion/archive decisions are sensitive.
- The system suggests actions, but the user confirms before Gmail is modified.
- Local state is mirrored after Gmail changes so the dashboard stays consistent.
- Health score is formula-based, so it is explainable rather than vague AI magic.

Health score formula:

```text
100 - unread_ratio*30 - high_priority_unread*4 - pending_reply_ratio*25 - aged_follow_up*6 - cleanup_candidate_ratio*20
```

## 10. Data Model

| Table | Responsibility | Key Design Point |
| --- | --- | --- |
| `users` | MailMind user identity and auth profile. | One user owns accounts, emails, jobs, and AI usage. |
| `gmail_accounts` | Connected Gmail account metadata. | Stores encrypted refresh token and latest Gmail `history_id`. |
| `email_threads` | Gmail conversation/thread grouping. | Enables thread summaries and ordered thread views. |
| `emails` | Synced Gmail message data plus latest AI/search state. | Uses Gmail message identity for idempotent sync. |
| `sync_jobs` | Background sync observability. | Tracks queued/running/retrying/succeeded/failed states. |
| `email_classifications` | Append-only AI classification audit log. | Stores confidence, model version, and label output history. |
| `email_feedback` | Human corrections to AI labels. | Supports future evaluation and retraining. |
| `ai_usage_logs` | AI token and cost events. | Lets the app report usage/cost per user and feature. |

## 11. Important Design Decisions

| Decision | Why It Was Used |
| --- | --- |
| FastAPI | Simple Python backend with type hints, dependency injection, and automatic OpenAPI docs. |
| SQLAlchemy + Alembic | Keeps database models and schema migrations versioned and maintainable. |
| PostgreSQL | Reliable relational storage for users, Gmail accounts, emails, sync jobs, and AI logs. |
| Redis + Celery | Moves long Gmail sync work outside request/response cycle. |
| Encrypted refresh tokens | Protects long-lived Gmail credentials at rest. |
| Idempotent upsert | Makes retries safe and prevents duplicate emails. |
| Gmail `historyId` | Enables incremental re-sync instead of expensive full re-fetch. |
| Two-stage classifier | Reduces LLM usage and gives deterministic behavior for obvious categories. |
| pgvector + full-text + RRF | Combines exact keyword matching with semantic retrieval. |
| Review-first cleanup | Avoids unsafe automatic email deletion/archive behavior. |
| Feedback log | Turns user corrections into future evaluation/retraining data. |
| Rate limiting | Protects expensive Gmail and AI routes from abuse or accidental repeated calls. |
| AI usage ledger | Makes token/cost behavior visible per user and feature. |

## 12. Interview Answer: Hardest Part

> The hardest part was designing Gmail sync reliability. External APIs can timeout, rate-limit, return partial data, or fail halfway. If a sync retries, the same Gmail messages may be fetched again. I handled this with background jobs, job states, retry handling, Gmail `historyId`, and idempotent database upserts using Gmail message IDs. The key idea is that reliability is not only retrying; it is safe retrying with database-level correctness.

## 13. What To Improve Next

- Run classification evaluation on a larger labeled dataset instead of a small smoke-test set.
- Use staged real-inbox sync limits before attempting a full 12000+ email import.
- Benchmark hybrid search with more labeled search queries and compare keyword-only, vector-only, and hybrid RRF.
- Add production metrics dashboards for sync latency, Gmail API failures, and AI cost trends.
- Add more granular cleanup actions such as unsubscribe detection, batch archive by sender, and undo history.
- Deploy with production secrets, HTTPS, managed PostgreSQL, and worker monitoring.
