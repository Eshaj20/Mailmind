# Demo Inbox Mode

Demo inbox mode lets MailMind run end-to-end without real Gmail OAuth, Google Cloud billing, or personal email data.

It creates:

- Demo user: `demo@mailmind.dev`
- Demo password: `DemoPass123!`
- Fake connected Gmail account
- Realistic synthetic inbox with recruiter, bills, travel, shopping, social, newsletter, security, and spam-like emails
- AI classification snapshots and append-only classification logs
- Thread summaries
- Search index data
- A succeeded sync job so the dashboard shows a realistic sync state

## When To Use This

Use demo mode when:

- You do not want to add card details for Google Cloud.
- You want a safe deployed portfolio demo.
- You want recruiters to see the full product flow immediately.
- You want screenshots or a demo video without exposing personal Gmail data.

## Run Locally With Docker

Start the stack:

```bash
docker compose up -d --build
```

Seed demo data:

```bash
docker compose exec backend python -m scripts.seed_demo_inbox --count 150 --reset
```

Open the app:

```text
http://localhost:5173
```

Login with:

```text
Email: demo@mailmind.dev
Password: DemoPass123!
```

## Run Without Docker

From `backend/`:

```bash
python -m scripts.seed_demo_inbox --count 150 --reset
```

## What To Show In A Demo

Recommended demo flow:

1. Login as the demo user.
2. Show the connected Gmail-style account.
3. Show latest synced emails.
4. Show classification summary and AI usage.
5. Search for examples like:
   - `interview schedule`
   - `electricity bill`
   - `flight ticket`
   - `security alert`
   - `unsubscribe newsletter`
6. Show inbox health score.
7. Open `/cleanup` from the dashboard and show the dedicated cleanup review workflow.
8. Apply archive or mark-read on synthetic emails only.
9. Show sender intelligence.

## Interview Talking Point

> I added a demo inbox mode so the SaaS can be evaluated without requiring a recruiter to connect Gmail or requiring me to expose personal email data. The seed script creates a realistic synthetic Gmail account, emails, classifications, search indexes, thread summaries, and sync job history using the same backend services as the main app. This makes the deployed app immediately usable while keeping real Gmail OAuth as an optional production integration.

## Important Note

Demo mode is not a replacement for real Gmail evaluation. It is for safe UX demos. For real model/search metrics, use the real inbox workflow in `docs/real-inbox-evaluation.md`.