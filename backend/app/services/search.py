from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import math
import re

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.gmail import Email
from app.models.user import User

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class SearchResult:
    email: Email
    keyword_rank: int | None
    vector_rank: int | None
    keyword_score: float
    vector_score: float
    rrf_score: float
    match_reason: str


def build_email_search_text(email: Email) -> str:
    # Keep this as the single source of truth for what gets searched. Any new
    # searchable email field should be added here before re-indexing emails.
    return " ".join(
        part.strip()
        for part in [
            email.sender or "",
            email.recipients or "",
            email.subject or "",
            email.snippet or "",
            email.body_preview or "",
            email.category or "",
            email.priority or "",
        ]
        if part and part.strip()
    )


def tokenize(text_value: str) -> list[str]:
    return TOKEN_PATTERN.findall(text_value.lower())


def embed_text(text_value: str, dimensions: int | None = None) -> list[float]:
    """Deterministic embedding for local demos, tests, and pgvector storage.

    Production can swap this function to an OpenAI embedding call without changing
    the DB/search contract. Today it gives stable vectors without network/cost.
    """
    dimensions = dimensions or settings.embedding_dimensions
    vector = [0.0] * dimensions
    for token in tokenize(text_value):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [round(value / norm, 6) for value in vector]


def ensure_email_search_index(email: Email) -> None:
    # Recompute only when the searchable text/model changes. This avoids doing
    # repeated embedding work during idempotent Gmail re-syncs.
    text_value = build_email_search_text(email)
    if (
        email.search_text == text_value
        and email.search_embedding
        and email.search_embedding_model == settings.embedding_model
    ):
        return

    email.search_text = text_value
    email.search_embedding = embed_text(text_value)
    email.search_embedding_model = settings.embedding_model
    email.search_embedded_at = datetime.now(UTC)


def ensure_user_search_index(db: Session, user: User) -> int:
    emails = list(db.scalars(select(Email).where(Email.user_id == user.id)))
    updated = 0
    postgres_updates: list[tuple[int, list[float]]] = []
    for email in emails:
        before = (email.search_text, email.search_embedding, email.search_embedding_model)
        ensure_email_search_index(email)
        after = (email.search_text, email.search_embedding, email.search_embedding_model)
        if before != after:
            updated += 1
        if _is_postgres(db) and email.search_embedding:
            postgres_updates.append((email.id, email.search_embedding))

    if updated:
        db.flush()
    if postgres_updates:
        _sync_pgvector_embeddings(db, postgres_updates)
    if updated or postgres_updates:
        db.commit()
    return updated


def hybrid_search_emails(db: Session, user: User, query: str, limit: int = 10) -> list[SearchResult]:
    # Search is always scoped by the authenticated MailMind user. This prevents
    # one user's Gmail data from appearing in another user's search results.
    ensure_user_search_index(db, user)
    if _is_postgres(db):
        return _hybrid_search_postgres(db, user, query, limit)
    return _hybrid_search_python(db, user, query, limit)


def _hybrid_search_postgres(db: Session, user: User, query: str, limit: int) -> list[SearchResult]:
    # Postgres path: run keyword and semantic retrieval separately, then merge
    # by rank. Keeping them separate makes benchmarking keyword-only/vector-only
    # straightforward later.
    query_embedding = _vector_literal(embed_text(query))
    keyword_rows = db.execute(
        text(
            """
            SELECT id,
                   row_number() OVER (ORDER BY keyword_score DESC, received_at DESC NULLS LAST, id DESC) AS rank,
                   keyword_score
            FROM (
                SELECT id, received_at, ts_rank_cd(search_document, websearch_to_tsquery('english', :query)) AS keyword_score
                FROM emails
                WHERE user_id = :user_id
                  AND search_document @@ websearch_to_tsquery('english', :query)
            ) ranked
            ORDER BY rank
            LIMIT :limit
            """
        ),
        {"query": query, "user_id": user.id, "limit": limit * 4},
    ).mappings()
    vector_rows = db.execute(
        text(
            """
            SELECT id,
                   row_number() OVER (ORDER BY distance ASC, received_at DESC NULLS LAST, id DESC) AS rank,
                   1 - distance AS vector_score
            FROM (
                SELECT id, received_at, search_embedding_vector <=> CAST(:query_embedding AS vector) AS distance
                FROM emails
                WHERE user_id = :user_id
                  AND search_embedding_vector IS NOT NULL
            ) ranked
            ORDER BY rank
            LIMIT :limit
            """
        ),
        {"query_embedding": query_embedding, "user_id": user.id, "limit": limit * 4},
    ).mappings()

    return _merge_ranked_rows(db, keyword_rows, vector_rows, limit)


def _hybrid_search_python(db: Session, user: User, query: str, limit: int) -> list[SearchResult]:
    # SQLite/test fallback mirrors the same retrieval idea without pgvector or
    # Postgres full-text search, keeping CI fast and dependency-light.
    query_tokens = tokenize(query)
    query_embedding = embed_text(query)
    emails = list(db.scalars(select(Email).where(Email.user_id == user.id)))

    keyword_ranked = sorted(
        [
            (email, _keyword_score(query_tokens, email.search_text or build_email_search_text(email)))
            for email in emails
        ],
        key=lambda item: (item[1], item[0].received_at or item[0].created_at),
        reverse=True,
    )
    keyword_rows = [
        {"id": email.id, "rank": rank, "keyword_score": score}
        for rank, (email, score) in enumerate(keyword_ranked, start=1)
        if score > 0
    ]

    vector_ranked = sorted(
        [
            (email, _cosine_similarity(query_embedding, email.search_embedding or []))
            for email in emails
        ],
        key=lambda item: (item[1], item[0].received_at or item[0].created_at),
        reverse=True,
    )
    vector_rows = [
        {"id": email.id, "rank": rank, "vector_score": score}
        for rank, (email, score) in enumerate(vector_ranked, start=1)
        if score > 0
    ]

    return _merge_ranked_rows(db, keyword_rows, vector_rows, limit)


def _merge_ranked_rows(db: Session, keyword_rows, vector_rows, limit: int) -> list[SearchResult]:
    # RRF uses rank positions instead of raw scores, which is useful because
    # Postgres text-rank scores and vector cosine scores are not comparable.
    keyword_rank_by_id: dict[int, int] = {}
    keyword_score_by_id: dict[int, float] = {}
    for row in keyword_rows:
        email_id = int(row["id"])
        keyword_rank_by_id[email_id] = int(row["rank"])
        keyword_score_by_id[email_id] = float(row["keyword_score"])

    vector_rank_by_id: dict[int, int] = {}
    vector_score_by_id: dict[int, float] = {}
    for row in vector_rows:
        email_id = int(row["id"])
        vector_rank_by_id[email_id] = int(row["rank"])
        vector_score_by_id[email_id] = float(row["vector_score"])

    ids = set(keyword_rank_by_id) | set(vector_rank_by_id)
    if not ids:
        return []

    emails = {email.id: email for email in db.scalars(select(Email).where(Email.id.in_(ids)))}
    results: list[SearchResult] = []
    for email_id in ids:
        email = emails[email_id]
        keyword_rank = keyword_rank_by_id.get(email_id)
        vector_rank = vector_rank_by_id.get(email_id)
        rrf_score = _rrf_score(keyword_rank, vector_rank)
        results.append(
            SearchResult(
                email=email,
                keyword_rank=keyword_rank,
                vector_rank=vector_rank,
                keyword_score=round(keyword_score_by_id.get(email_id, 0.0), 4),
                vector_score=round(vector_score_by_id.get(email_id, 0.0), 4),
                rrf_score=round(rrf_score, 6),
                match_reason=_match_reason(keyword_rank, vector_rank),
            )
        )

    return sorted(
        results,
        key=lambda result: (result.rrf_score, result.email.received_at or result.email.created_at),
        reverse=True,
    )[:limit]


def _sync_pgvector_embeddings(db: Session, email_vectors: list[tuple[int, list[float]]]) -> None:
    # SQLAlchemy stores the portable JSON embedding; this mirrors it into the
    # Postgres vector column used by the IVFFlat index.
    for email_id, vector in email_vectors:
        db.execute(
            text(
                """
                UPDATE emails
                SET search_embedding_vector = CAST(:embedding AS vector)
                WHERE id = :email_id
                """
            ),
            {"embedding": _vector_literal(vector), "email_id": email_id},
        )


def _keyword_score(query_tokens: list[str], text_value: str) -> float:
    if not query_tokens:
        return 0.0
    text_tokens = tokenize(text_value)
    if not text_tokens:
        return 0.0
    text_counts: dict[str, int] = {}
    for token in text_tokens:
        text_counts[token] = text_counts.get(token, 0) + 1
    exact_hits = sum(text_counts.get(token, 0) for token in query_tokens)
    phrase_bonus = 2 if " ".join(query_tokens) in text_value.lower() else 0
    return float(exact_hits + phrase_bonus)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def _rrf_score(keyword_rank: int | None, vector_rank: int | None) -> float:
    score = 0.0
    if keyword_rank is not None:
        score += 1 / (settings.search_rrf_k + keyword_rank)
    if vector_rank is not None:
        score += 1 / (settings.search_rrf_k + vector_rank)
    return score


def _match_reason(keyword_rank: int | None, vector_rank: int | None) -> str:
    if keyword_rank is not None and vector_rank is not None:
        return "keyword_and_semantic"
    if keyword_rank is not None:
        return "keyword"
    return "semantic"


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(str(value) for value in vector) + "]"


def _is_postgres(db: Session) -> bool:
    return db.bind is not None and db.bind.dialect.name == "postgresql"

