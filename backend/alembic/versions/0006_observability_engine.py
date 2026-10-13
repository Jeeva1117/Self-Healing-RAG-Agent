"""Phase 10: Observability and distributed tracing tables.

Revision ID: 0006_observability
Revises: 0005_eval_engine
Create Date: 2026-10-10 17:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic (must be <= 32 chars)
revision: str = "0006_observability"
down_revision: str | None = "0005_eval_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. execution_traces table
    op.create_table(
        "execution_traces",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("trace_id", sa.String(length=64), unique=True, nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("knowledge_base_id", sa.Uuid(as_uuid=True), sa.ForeignKey("knowledge_bases.id", ondelete="SET NULL"), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="completed"),
        sa.Column("duration_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("tokens_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("model", sa.String(length=100), nullable=False, server_default="default"),
        sa.Column("error_category", sa.String(length=100), nullable=True),
        sa.Column("recovery_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("trace_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_execution_traces_user_status", "execution_traces", ["user_id", "status"])
    op.create_index("ix_execution_traces_status_created", "execution_traces", ["status", "created_at"])
    op.create_index("ix_execution_traces_trace_id", "execution_traces", ["trace_id"])
    op.create_index("ix_execution_traces_error_category", "execution_traces", ["error_category"])

    # 2. trace_spans table
    op.create_table(
        "trace_spans",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("trace_id", sa.String(length=64), sa.ForeignKey("execution_traces.trace_id", ondelete="CASCADE"), nullable=False),
        sa.Column("span_id", sa.String(length=64), nullable=False),
        sa.Column("parent_span_id", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("step_type", sa.String(length=50), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="completed"),
        sa.Column("inputs", sa.JSON(), nullable=True),
        sa.Column("outputs", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("span_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_trace_spans_trace_step", "trace_spans", ["trace_id", "step_type"])
    op.create_index("ix_trace_spans_span_id", "trace_spans", ["span_id"])


def downgrade() -> None:
    op.drop_table("trace_spans")
    op.drop_table("execution_traces")
