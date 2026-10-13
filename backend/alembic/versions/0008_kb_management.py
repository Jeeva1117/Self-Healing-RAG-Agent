"""Phase 12: Knowledge Base Management, Health, and Repair Jobs.

Revision ID: 0008_kb_management
Revises: 0007_production_intel
Create Date: 2026-10-10 22:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic (must be <= 32 chars)
revision: str = "0008_kb_management"
down_revision: str | None = "0007_production_intel"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create kb_repair_jobs table
    op.create_table(
        "kb_repair_jobs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "knowledge_base_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="PENDING"),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("findings_addressed", sa.JSON(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_kb_repair_jobs_id"), "kb_repair_jobs", ["id"], unique=False)
    op.create_index(op.f("ix_kb_repair_jobs_knowledge_base_id"), "kb_repair_jobs", ["knowledge_base_id"], unique=False)
    op.create_index(op.f("ix_kb_repair_jobs_document_id"), "kb_repair_jobs", ["document_id"], unique=False)
    op.create_index(op.f("ix_kb_repair_jobs_user_id"), "kb_repair_jobs", ["user_id"], unique=False)
    op.create_index(op.f("ix_kb_repair_jobs_action"), "kb_repair_jobs", ["action"], unique=False)
    op.create_index(op.f("ix_kb_repair_jobs_status"), "kb_repair_jobs", ["status"], unique=False)
    op.create_index("ix_kb_repair_jobs_kb_status", "kb_repair_jobs", ["knowledge_base_id", "status"], unique=False)
    op.create_index("ix_kb_repair_jobs_doc_status", "kb_repair_jobs", ["document_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_kb_repair_jobs_doc_status", table_name="kb_repair_jobs")
    op.drop_index("ix_kb_repair_jobs_kb_status", table_name="kb_repair_jobs")
    op.drop_index(op.f("ix_kb_repair_jobs_status"), table_name="kb_repair_jobs")
    op.drop_index(op.f("ix_kb_repair_jobs_action"), table_name="kb_repair_jobs")
    op.drop_index(op.f("ix_kb_repair_jobs_user_id"), table_name="kb_repair_jobs")
    op.drop_index(op.f("ix_kb_repair_jobs_document_id"), table_name="kb_repair_jobs")
    op.drop_index(op.f("ix_kb_repair_jobs_knowledge_base_id"), table_name="kb_repair_jobs")
    op.drop_index(op.f("ix_kb_repair_jobs_id"), table_name="kb_repair_jobs")
    op.drop_table("kb_repair_jobs")
