"""Phase 11: Production intelligence, token accounting, and cost tracking.

Revision ID: 0007_production_intel
Revises: 0006_observability
Create Date: 2026-10-10 20:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic (must be <= 32 chars)
revision: str = "0007_production_intel"
down_revision: str | None = "0006_observability"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. execution_traces columns
    op.add_column("execution_traces", sa.Column("prompt_tokens", sa.Integer(), nullable=True))
    op.add_column("execution_traces", sa.Column("completion_tokens", sa.Integer(), nullable=True))
    op.add_column("execution_traces", sa.Column("estimated_cost_usd", sa.Float(), nullable=True))
    op.add_column("execution_traces", sa.Column("cost_status", sa.String(length=50), nullable=True, server_default="unavailable"))
    op.add_column("execution_traces", sa.Column("cost_currency", sa.String(length=10), nullable=True, server_default="USD"))
    op.add_column("execution_traces", sa.Column("pricing_source", sa.String(length=100), nullable=True))
    op.add_column("execution_traces", sa.Column("retrieval_method", sa.String(length=50), nullable=True))
    op.add_column("execution_traces", sa.Column("retrieval_scores", sa.JSON(), nullable=True))
    op.add_column("execution_traces", sa.Column("evidence_sufficiency", sa.String(length=50), nullable=True))
    op.add_column("execution_traces", sa.Column("citation_validation_passed", sa.Boolean(), nullable=True))
    op.add_column("execution_traces", sa.Column("verification_status", sa.String(length=50), nullable=True))

    # 2. trace_spans columns
    op.add_column("trace_spans", sa.Column("prompt_tokens", sa.Integer(), nullable=True))
    op.add_column("trace_spans", sa.Column("completion_tokens", sa.Integer(), nullable=True))
    op.add_column("trace_spans", sa.Column("estimated_cost_usd", sa.Float(), nullable=True))
    op.add_column("trace_spans", sa.Column("is_skipped", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("trace_spans", "is_skipped")
    op.drop_column("trace_spans", "estimated_cost_usd")
    op.drop_column("trace_spans", "completion_tokens")
    op.drop_column("trace_spans", "prompt_tokens")

    op.drop_column("execution_traces", "verification_status")
    op.drop_column("execution_traces", "citation_validation_passed")
    op.drop_column("execution_traces", "evidence_sufficiency")
    op.drop_column("execution_traces", "retrieval_scores")
    op.drop_column("execution_traces", "retrieval_method")
    op.drop_column("execution_traces", "pricing_source")
    op.drop_column("execution_traces", "cost_currency")
    op.drop_column("execution_traces", "cost_status")
    op.drop_column("execution_traces", "estimated_cost_usd")
    op.drop_column("execution_traces", "completion_tokens")
    op.drop_column("execution_traces", "prompt_tokens")
