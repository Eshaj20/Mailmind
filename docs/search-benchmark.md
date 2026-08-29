# Search Benchmark Notes

MailMind uses hybrid search instead of vector-only retrieval:

1. PostgreSQL full-text search finds exact keyword matches.
2. pgvector cosine search finds semantic matches.
3. Reciprocal Rank Fusion merges both ranked lists.

## Benchmark Goal

Compare:

- keyword-only
- vector-only
- hybrid RRF

Use `backend/scripts/benchmark_search.py` with `backend/eval/search_queries.example.csv` or a larger labeled query set.

```bash
cd backend
python -m scripts.benchmark_search --input eval/search_queries.example.csv --user-email you@example.com
```

The script writes both:

- `eval/search_benchmark.json` for full per-query details.
- `eval/search_benchmark.md` for a README-ready summary table.

## Metrics

| Metric | Why it matters |
| --- | --- |
| Hit@1 | Whether the top result is the expected email |
| Hit@3 | Whether a useful email appears quickly |
| MRR | Whether the correct result is ranked near the top |

## Output Table

The Markdown report uses this format:

| Mode | Hit@1 | Hit@3 | MRR |
| --- | ---: | ---: | ---: |
| keyword | generated after running benchmark | generated after running benchmark | generated after running benchmark |
| vector | generated after running benchmark | generated after running benchmark | generated after running benchmark |
| hybrid | generated after running benchmark | generated after running benchmark | generated after running benchmark |

## Current Status

The benchmark implementation is ready, but real search quality numbers need a synced inbox and labeled query set with actual `expected_email_id` values. The included CSV is intentionally tiny and only demonstrates the file format.

## Interview Talking Point

Vector-only search is not always best for email because users often remember exact terms like company names, invoice numbers, names, or dates. Hybrid search keeps exact keyword recall while adding semantic matching for vague queries like "interview follow up" or "electricity bill".
