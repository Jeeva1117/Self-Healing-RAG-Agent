"""Phase 13: Data Sources and External Connectors.

Revision ID: 0009_data_sources
Revises: 0008_kb_management
Create Date: 2026-10-12 22:50:00.000000

"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "0009_data_sources"
down_revision: str | None = "0008_kb_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_sources",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "knowledge_base_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("knowledge_bases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="not_configured"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_status", sa.String(length=50), nullable=True),
        sa.Column("last_sync_error", sa.String(length=1000), nullable=True),
        sa.Column("synced_documents_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("synced_chunks_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_data_sources_id"), "data_sources", ["id"], unique=False)
    op.create_index(op.f("ix_data_sources_user_id"), "data_sources", ["user_id"], unique=False)
    op.create_index(op.f("ix_data_sources_knowledge_base_id"), "data_sources", ["knowledge_base_id"], unique=False)
    op.create_index(op.f("ix_data_sources_source_type"), "data_sources", ["source_type"], unique=False)
    op.create_index(op.f("ix_data_sources_status"), "data_sources", ["status"], unique=False)
    op.create_index("ix_data_sources_user_type", "data_sources", ["user_id", "source_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_data_sources_user_type", table_name="data_sources")
    op.drop_index(op.f("ix_data_sources_status"), table_name="data_sources")
    op.drop_index(op.f("ix_data_sources_source_type"), table_name="data_sources")
    op.drop_index(op.f("ix_data_sources_knowledge_base_id"), table_name="data_sources")
    op.drop_index(op.f("ix_data_sources_user_id"), table_name="data_sources")
    op.drop_index(op.f("ix_data_sources_id"), table_name="data_sources")
    op.drop_table("data_sources")
