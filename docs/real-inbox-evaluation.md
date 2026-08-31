# Real Gmail Evaluation Workflow

This workflow is for testing MailMind on a real Gmail inbox without accidentally committing private email data.

## Goal

Use a real inbox to produce trustworthy project numbers:

- Classification precision/recall/F1 on 100-150 hand-labeled real emails.
- Search Hit@1, Hit@3, and MRR on 20-30 real search queries.
- Sync reliability evidence across progressively larger Gmail batches.

Before connecting a private Gmail account, run the synthetic large-inbox benchmark in `docs/large-inbox-benchmark.md`. It gives safe scalability numbers for classification coverage, spam-risk scoring, cleanup preview, and search latency without exposing personal email content.

## Safety Rules

- Do not commit real exported email CSVs.
- Keep `.env` private.
- Start with small sync limits before trying thousands of emails.
- Use review-first cleanup; do not auto-delete emails.
- Prefer `archive` and `mark_read` actions only after preview.

Private outputs are ignored by Git under:

```text
backend/eval/private/
```

## Step 1: Configure Gmail OAuth

Add local credentials in `.env`:

```env
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/gmail/oauth/callback
GMAIL_SCOPES=openid email profile https://www.googleapis.com/auth/gmail.modify
GMAIL_INITIAL_SYNC_MAX_RESULTS=25
```

Keep the default first sync small. `GMAIL_SYNC_QUERY=newer_than:30d` keeps early tests recent and safer; for a full historical inbox experiment, widen this query or leave it blank only after smaller sync stages are stable. The dashboard and API now support per-job sync limits for controlled scaling.

## Step 2: Start The Stack

```bash
docker compose up --build
```

Open:

```text
http://localhost:5173
```

Sign up, log in, and connect Gmail from the dashboard.

## Step 3: Scale Sync Gradually

Recommended sync ramp:

| Stage | Sync Limit | What To Check |
| --- | ---: | --- |
| Smoke | 25 | OAuth, first sync, dashboard renders. |
| Small real run | 100 | Classification/search work on real inbox shape. |
| Medium run | 500 | Worker stability, no duplicate rows. |
| Larger run | 1000-5000 | Sync duration, retries, rate limits, DB size. |
| Full run | 12000+ | Only after smaller stages are stable. |

From the dashboard, choose the sync size before clicking Queue sync.

API equivalent:

```bash
curl -X POST "http://localhost:8000/api/v1/gmail/sync?max_results=100" \
  -H "Authorization: Bearer <jwt>"
```

## Step 4: Export Real Emails For Labeling

From `backend/`:

```bash
python -m scripts.export_emails_for_labeling \
  --email your-mailmind-login@example.com \
  --limit 150 \
  --output eval/private/labeled_emails_real.csv
```

Hand-label these columns:

| Column | Allowed Values |
| --- | --- |
| `label_category` | `primary`, `promotions`, `social`, `updates`, `spam` |
| `label_priority` | `high`, `medium`, `low` |
| `label_needs_reply` | `true`, `false` |

## Step 5: Run Real Classification Evaluation

From `backend/`:

```bash
python -m scripts.evaluate_classifier \
  --input eval/private/labeled_emails_real.csv \
  --output eval/private/eval_report_real.md
```

Use these numbers only after manual labeling is complete.

## Step 6: Build Real Search Benchmark

Create `backend/eval/private/search_queries_real.csv`:

```csv
query,expected_email_id
"electricity bill",123
"interview schedule",456
```

Use actual `emails.id` values from your synced database. Aim for 20-30 realistic queries.

Run:

```bash
python -m scripts.benchmark_search \
  --input eval/private/search_queries_real.csv \
  --user-email your-mailmind-login@example.com \
  --output eval/private/search_benchmark_real.json \
  --markdown-output eval/private/search_benchmark_real.md
```

The report compares:

- keyword-only
- vector-only
- hybrid RRF

Metrics:

| Metric | Meaning |
| --- | --- |
| Hit@1 | Expected email is the top result. |
| Hit@3 | Expected email appears in top 3 results. |
| MRR | Expected email is ranked close to the top. |

## Step 7: Update Public README With Safe Numbers

Only copy aggregate metrics, never real email rows/snippets.

Good README table format:

| Evaluation | Dataset | Metric |
| --- | --- | --- |
| Classification | 150 real hand-labeled emails | Category Macro F1: `x.xxx` |
| Classification | 150 real hand-labeled emails | Needs-reply Macro F1: `x.xxx` |
| Search | 30 real labeled queries | Hybrid Hit@3: `x.xxx`, MRR: `x.xxx` |
| Sync | 5000 real emails | `0` duplicate rows on re-sync |

## Interview Talking Point

> I first validated the system on a small synthetic seed set, then moved to a real Gmail inbox in stages. I avoided syncing all 12k emails at once. Each sync job stores its own max_results limit, which let me test 25, 100, 500, and larger batches safely. For model quality, I exported a private 100-150 email set, hand-labeled it, and evaluated precision/recall/F1. For search quality, I benchmarked keyword-only, vector-only, and hybrid RRF retrieval on labeled real queries.