# Large Inbox Benchmark

MailMind supports a synthetic large-inbox benchmark so we can test the full product flow without exposing private Gmail data or requiring Google Cloud billing during demos.

## What This Proves

- The database can hold thousands of Gmail-like messages for one user.
- Classification, spam-risk scoring, and search indexing run on every email.
- Cleanup preview ranks noisy/promotional/spam-risk emails at product scale.
- Hybrid search latency can be measured across keyword, vector, and RRF modes.
- The seeded inbox is idempotent: re-running with the same count does not create duplicate Gmail message rows.

## Seed A Large Inbox

From `backend/`:

```bash
python -m scripts.seed_large_inbox --count 10000 --reset
```

This creates:

```text
login: large@mailmind.local
password: LargePass123!
gmail account: large.inbox@mailmind.local
```

Use a smaller count while developing:

```bash
python -m scripts.seed_large_inbox --count 1000 --reset --batch-size 250
```

## Run Benchmark

From `backend/`:

```bash
python -m scripts.benchmark_large_inbox --seed-count 10000 --reset
```

Outputs:

```text
backend/eval/large_inbox_benchmark.json
backend/eval/large_inbox_benchmark.md
```

## Metrics Captured

| Metric | Why It Matters |
| --- | --- |
| Total emails | Confirms large inbox size. |
| Classified emails | Confirms AI pipeline coverage. |
| Spam-risk emails | Shows cleanup-specific signal volume. |
| Cleanup candidates | Shows how many emails MailMind can recommend for review. |
| Search index warmup latency | Separates one-time pgvector mirror/index preparation from steady-state search. |
| Inbox health latency | Measures dashboard intelligence cost. |
| Cleanup preview latency | Measures cleanup recommendation speed. |
| Avg/P95 search latency | Measures retrieval experience across keyword, vector, and hybrid modes. |

## Resume-Safe Claim

After running the benchmark, use aggregate numbers only:

> Benchmarked MailMind on 10k+ synthetic Gmail-like records, validating classification coverage, spam-risk scoring, hybrid search latency, cleanup ranking, and idempotent large-inbox seeding without exposing private email data.