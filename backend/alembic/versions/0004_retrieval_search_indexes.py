"""Phase 5: Retrieval and Search Indexes (Full-Text Search GIN Index)

Revision ID: 0004_retrieval_indexes
Revises: 0003_kb_and_documents
Create Date: 2026-10-09 17:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic (must be <= 32 chars)
revision: str = "0004_retrieval_indexes"
down_revision: str | None = "0003_kb_and_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        # Create GIN index on to_tsvector('english', content) for PostgreSQL full-text search
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_document_chunks_content_tsv
            ON document_chunks USING gin (to_tsvector('english', content));
            """
        )
        # Create compound index for model tracking and chunk lookups
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_document_chunks_model_dim
            ON document_chunks (embedding_model, embedding_dimension);
            """
        )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_model_dim;")
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_content_tsv;")
