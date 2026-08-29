# MailMind API Reference

Base URL: `/api/v1`

Most Gmail, sync, AI, search, and cleanup endpoints require:

```http
Authorization: Bearer <jwt_access_token>
```

## Health

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/healthz` | No | Confirms the FastAPI service is running. |

Example response:

```json
{
  "status": "ok"
}
```

## Authentication

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `/auth/signup` | No | Creates a MailMind user with hashed password storage. |
| `POST` | `/auth/login` | No | Verifies credentials and returns a JWT access token. |
| `GET` | `/auth/me` | Yes | Returns the current authenticated user. |

Signup body:

```json
{
  "email": "user@example.com",
  "password": "strong-password",
  "full_name": "User Name"
}
```

Login body:

```json
{
  "email": "user@example.com",
  "password": "strong-password"
}
```

Token response:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

## Gmail OAuth And Accounts

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/gmail/oauth/authorize` | Yes | Builds the Google OAuth consent URL with a MailMind state token. |
| `GET` | `/gmail/oauth/callback` | No | Handles Google's browser redirect with `code` and `state`. |
| `POST` | `/gmail/oauth/callback` | No | Test-friendly callback path with JSON payload. |
| `GET` | `/gmail/accounts` | Yes | Lists Gmail accounts connected by the current user. |

Callback body for `POST /gmail/oauth/callback`:

```json
{
  "code": "google-oauth-code",
  "state": "mailmind-oauth-state"
}
```

Connected account fields:

| Field | Meaning |
| --- | --- |
| `id` | Internal Gmail account id. |
| `google_email` | Connected Gmail address. |
| `history_id` | Gmail incremental sync cursor. |
| `sync_status` | Current account-level sync status. |
| `last_synced_at` | Last successful sync timestamp. |

## Sync Jobs

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `/gmail/sync` | Yes | Queues an async Gmail re-sync job. |
| `GET` | `/gmail/sync/jobs` | Yes | Lists sync jobs for the current user. |
| `GET` | `/gmail/sync/jobs/{job_id}` | Yes | Fetches one sync job by id. |
| `GET` | `/gmail/sync/health` | Yes | Summarizes sync reliability and recent job status. |

Optional query parameter for `POST /gmail/sync`:

| Query | Meaning |
| --- | --- |
| `account_id` | Sync one connected Gmail account; otherwise uses the user's first matching account. |

Sync job fields:

| Field | Meaning |
| --- | --- |
| `status` | `queued`, `running`, `retrying`, `succeeded`, or `failed`. |
| `attempt_count` | Number of attempts already made. |
| `max_attempts` | Retry ceiling before permanent failure. |
| `synced_count` | Gmail messages processed. |
| `created_count` | New email rows inserted. |
| `updated_count` | Existing email rows updated by idempotent upsert. |
| `error_type` / `error_message` | Observability fields for debugging Gmail/API failures. |

Sync health response includes job counts by status, latest status, last successful sync time, average synced count, and error counts grouped by error type.

## Emails And Search

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/gmail/emails` | Yes | Lists synced emails with pagination and filters. |
| `GET` | `/gmail/search` | Yes | Runs hybrid keyword + vector search with RRF ranking. |

Email list query parameters:

| Query | Default | Meaning |
| --- | --- | --- |
| `limit` | `25` | Page size, from 1 to 100. |
| `offset` | `0` | Offset for pagination. |
| `category` | None | Filter by AI category. |
| `priority` | None | Filter by AI priority. |
| `is_read` | None | Filter read/unread state. |
| `needs_reply` | None | Filter emails that likely need a reply. |
| `sender` | None | Case-insensitive sender substring search. |

Search query parameters:

| Query | Default | Meaning |
| --- | --- | --- |
| `q` | Required | User search query, 2 to 200 characters. |
| `limit` | `10` | Number of ranked results, from 1 to 25. |

Search result fields include:

| Field | Meaning |
| --- | --- |
| `keyword_rank` | Rank from PostgreSQL full-text search. |
| `vector_rank` | Rank from pgvector cosine similarity. |
| `keyword_score` | Full-text relevance score. |
| `vector_score` | Semantic similarity score. |
| `rrf_score` | Final Reciprocal Rank Fusion score. |
| `match_reason` | Human-readable reason explaining how the result matched. |

## Inbox Intelligence And Cleanup

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/gmail/insights` | Yes | Returns inbox health score, formula, and prioritized suggestions. |
| `GET` | `/gmail/cleanup/preview` | Yes | Shows safe cleanup candidates before any Gmail action is applied. |
| `POST` | `/gmail/cleanup/actions` | Yes | Applies user-confirmed cleanup actions through Gmail modify API. |
| `GET` | `/gmail/senders` | Yes | Groups noisy or important sender patterns. |
| `POST` | `/gmail/feedback` | Yes | Stores human corrections for AI labels and updates latest email snapshot. |

Cleanup action body:

```json
{
  "email_ids": [1, 2, 3],
  "action": "archive"
}
```

Supported cleanup actions:

| Action | Gmail effect | Local effect |
| --- | --- | --- |
| `archive` | Removes `INBOX` label. | Mirrors label change in PostgreSQL. |
| `mark_read` | Removes `UNREAD` label. | Sets `is_read=true`. |

Feedback body:

```json
{
  "email_id": 10,
  "feedback_type": "correction",
  "corrected_category": "recruiter",
  "corrected_priority": "high",
  "corrected_needs_reply": true,
  "note": "Interview email should be high priority."
}
```

## AI Classification, Evaluation, And Usage

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `/gmail/classify` | Yes | Classifies unclassified emails for the current user. |
| `GET` | `/gmail/classification/summary` | Yes | Aggregates classified/unclassified counts and label distribution. |
| `GET` | `/gmail/classification/evaluation` | Yes | Returns the generated precision/recall/F1 report. |
| `GET` | `/gmail/ai/usage` | Yes | Returns token and estimated cost tracking by user. |
| `GET` | `/gmail/threads` | Yes | Lists synced Gmail threads. |
| `POST` | `/gmail/threads/{thread_id}/summarize` | Yes | Generates or refreshes a thread summary. |

Classification output tracks category, priority, reply need, confidence, model version, and timestamp. The email row stores the latest label snapshot for fast reads, while classification logs preserve historical model outputs for audit and evaluation.

## Reliability Notes

- Gmail sync is async: API requests enqueue work, while Celery workers perform Gmail calls.
- Re-sync is idempotent: Gmail message IDs and database constraints/upsert logic prevent duplicate email rows.
- Retryable Gmail failures are tracked through job states and error fields.
- Cleanup is review-first: the system previews candidates and only modifies Gmail after explicit user action.
- AI usage is logged per user so token volume and estimated cost can be monitored.
