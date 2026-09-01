# Pre-Deployment Feature Checklist

Use this checklist before sharing the deployed MailMind link with recruiters or real users.

## Automated API Smoke

Seed demo data first:

```bash
python -m scripts.seed_demo_inbox --count 150 --reset
```

Run the smoke test:

```bash
python -m scripts.smoke_deployment --base-url http://localhost:8000/api/v1 --cleanup-undo
```

The smoke test covers:

| Feature Area | Covered Check |
| --- | --- |
| Health | `/healthz` and `/health` return OK. |
| Auth | Demo login and protected `/auth/me`. |
| Gmail account state | Demo Gmail account exists. |
| Email listing | Paginated email API returns demo emails. |
| Inbox intelligence | Health score and cleanup count are returned. |
| Cleanup | Preview works; optional action + undo works. |
| Search | Hybrid search returns ranked results. |
| Sync observability | Sync health endpoint returns job counts. |
| AI layer | Classification summary, classify endpoint, evaluation report, and usage ledger. |
| Sender/thread views | Sender insights and thread summaries load. |

## Manual Frontend Walkthrough

| Screen | Button/Control | Expected Result |
| --- | --- | --- |
| Auth | Signup/Login tabs | Form mode changes without layout break. |
| Auth | Use demo workspace | Fills demo credentials and switches to login. |
| Auth | Login | Navigates to dashboard with demo data. |
| Dashboard | Logout | Clears token and returns to auth flow. |
| Dashboard | Demo Gmail seeded | Disabled in demo mode; does not open Google OAuth. |
| Dashboard | Sync disabled in demo | Disabled in demo mode; does not queue fake Gmail sync. |
| Dashboard | Run AI classification | Safe no-op when all demo emails are already classified. |
| Dashboard | Search input | Shows ranked email results for queries like `electricity bill`. |
| Dashboard | Review cleanup | Opens `/cleanup`. |
| Dashboard | Select visible | Selects visible cleanup candidates. |
| Dashboard | Archive selected / Mark read | Applies reversible cleanup to selected demo emails. |
| Dashboard | Undo last cleanup | Restores labels/read state. |
| Dashboard | Archive / Mark read per item | Applies cleanup to one candidate. |
| Dashboard | Not cleanup | Records feedback and refreshes cleanup suggestions. |
| Dashboard | Previous/Next | Paginates latest email list. |
| Cleanup Review | Back to dashboard | Navigates back to `/`. |
| Cleanup Review | Logout | Clears token and returns to auth flow. |
| Cleanup Review | Filter chips | Filters candidate list locally. |
| Cleanup Review | Search candidates | Filters by subject/sender/reason. |
| Cleanup Review | Select visible | Toggles visible candidate selection. |
| Cleanup Review | Archive selected / Mark read | Applies reversible cleanup to selected visible emails. |
| Cleanup Review | Undo last cleanup | Restores last cleanup batch. |
| Cleanup Review | Not cleanup | Records feedback for a candidate. |

## Known Deployment Behavior

- Real Gmail OAuth requires Google credentials and production redirect URI.
- Demo mode is intentionally safe: real Gmail reconnect and re-sync controls are disabled.
- Cleanup in demo mode only updates local synthetic data; it does not call Gmail APIs.
- Real Gmail cleanup stays review-first and supports undo using local action logs.