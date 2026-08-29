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

## Suggested Metrics

| Metric | Why it matters |
| --- | --- |
| Hit@3 | Whether a useful email appears quickly |
| Hit@5 | Whether the result set contains the target email |
| MRR | Whether the correct result is ranked near the top |

## Interview Talking Point

Vector-only search is not always best for email because users often remember exact terms like company names, invoice numbers, names, or dates. Hybrid search keeps exact keyword recall while adding semantic matching for vague queries like "interview follow up" or "electricity bill".