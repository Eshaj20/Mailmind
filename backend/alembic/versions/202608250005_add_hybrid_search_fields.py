"""add hybrid search fields

Revision ID: 202608250005
Revises: 202608080004
Create Date: 2026-08-25 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202608250005"
down_revision: str | None = "202608080004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


VECTOR_DIMENSIONS = 64


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # JSON/text columns stay database-agnostic so SQLite tests can exercise the
    # search flow without requiring the Postgres-only pgvector extension.
    op.add_column("emails", sa.Column("search_text", sa.Text(), nullable=True))
    op.add_column("emails", sa.Column("search_embedding", sa.JSON(), nullable=True))
    op.add_column("emails", sa.Column("search_embedding_model", sa.String(length=64), nullable=True))
    op.add_column("emails", sa.Column("search_embedded_at", sa.DateTime(timezone=True), nullable=True))

    if dialect == "postgresql":
        # Production search uses Postgres full-text search for exact terms and
        # pgvector cosine search for semantic matches. The generated tsvector
        # column keeps keyword indexing consistent whenever search_text changes.
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute(f"ALTER TABLE emails ADD COLUMN search_embedding_vector vector({VECTOR_DIMENSIONS})")
        op.execute(
            """
            ALTER TABLE emails
            ADD COLUMN search_document tsvector
            GENERATED ALWAYS AS (to_tsvector('english', coalesce(search_text, ''))) STORED
            """
        )
        op.execute("CREATE INDEX ix_emails_search_document ON emails USING gin (search_document)")
        # IVFFlat is an approximate nearest-neighbor index. lists=100 is a
        # conservative starting point for portfolio-scale data and can be tuned
        # after benchmarking on a larger inbox dataset.
        op.execute(
            """
            CREATE INDEX ix_emails_search_embedding_vector
            ON emails USING ivfflat (search_embedding_vector vector_cosine_ops)
            WITH (lists = 100)
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_emails_search_embedding_vector")
        op.execute("DROP INDEX IF EXISTS ix_emails_search_document")
        op.execute("ALTER TABLE emails DROP COLUMN IF EXISTS search_document")
        op.execute("ALTER TABLE emails DROP COLUMN IF EXISTS search_embedding_vector")

    op.drop_column("emails", "search_embedded_at")
    op.drop_column("emails", "search_embedding_model")
    op.drop_column("emails", "search_embedding")
    op.drop_column("emails", "search_text")

