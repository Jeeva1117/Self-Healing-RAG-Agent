"""Pydantic schemas for Knowledge Base endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.infrastructure.database.models import KnowledgeBaseStatus


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120, description="Name of the knowledge base")
    description: str | None = Field(None, max_length=500, description="Optional description")


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = Field(None, max_length=500)
    status: KnowledgeBaseStatus | None = None


class KnowledgeBaseResponse(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    description: str | None = None
    status: KnowledgeBaseStatus
    created_at: datetime
    updated_at: datetime
    document_count: int = 0
    total_chunks: int = 0

    model_config = {"from_attributes": True}


class KnowledgeBaseListResponse(BaseModel):
    items: list[KnowledgeBaseResponse]
    total: int
    limit: int
    offset: int


# ==============================================================================
# Phase 12: Knowledge Base Management & Quality Intelligence Schemas
# ==============================================================================


class HealthFinding(BaseModel):
    """Specific explainable finding discovered during health evaluation."""

    code: str
    severity: str  # "error" | "warning" | "info"
    title: str
    message: str
    remediation: str
    is_repairable: bool = False
    affected_entity: str = "document"  # "document" | "version" | "chunk" | "knowledge_base"


class DocumentHealthReport(BaseModel):
    """Health check outcome for a specific document."""

    document_id: UUID
    filename: str
    status: str
    is_healthy: bool
    findings: list[HealthFinding] = []
    chunk_count: int = 0
    active_version: int = 1
    embedding_status: str = "valid"  # "valid" | "missing" | "inconsistent" | "none"
    last_indexed_at: datetime | None = None


class KnowledgeBaseHealthReport(BaseModel):
    """Comprehensive health evaluation across an entire knowledge base collection."""

    knowledge_base_id: UUID
    total_documents: int = 0
    healthy_documents: int = 0
    unhealthy_documents: int = 0
    stuck_documents: int = 0
    total_chunks: int = 0
    missing_embeddings_count: int = 0
    findings_summary: dict[str, int] = {}
    findings: list[HealthFinding] = []
    documents: list[DocumentHealthReport] = []


class DuplicateCandidate(BaseModel):
    """Detected exact or probable near-duplicate document within a knowledge base."""

    match_type: str  # "exact_checksum" | "exact_content" | "near_duplicate_text"
    similarity_score: float
    primary_document_id: UUID
    primary_filename: str
    duplicate_document_id: UUID
    duplicate_filename: str
    shared_checksum: str | None = None
    storage_impact_bytes: int = 0
    explanation: str


class DuplicateReport(BaseModel):
    """Knowledge base duplicate audit report."""

    knowledge_base_id: UUID
    exact_duplicates_count: int = 0
    near_duplicates_count: int = 0
    potential_storage_savings_bytes: int = 0
    candidates: list[DuplicateCandidate] = []


class CoverageGapItem(BaseModel):
    """Measured topic or query evidence gap from real execution history."""

    query: str
    frequency: int = 1
    avg_similarity: float | None = None
    gap_type: str = "insufficient_evidence"  # "insufficient_evidence" | "empty_retrieval" | "low_confidence"
    affected_topics: list[str] = []
    suggested_action: str


class CoverageReport(BaseModel):
    """Knowledge coverage and evidence sufficiency gap analysis."""

    knowledge_base_id: UUID
    total_queries_analyzed: int = 0
    insufficient_evidence_rate: float = 0.0
    unretrieved_documents: list[dict[str, object]] = []
    evidence_gaps: list[CoverageGapItem] = []
    recommendations: list[str] = []


class ConflictItem(BaseModel):
    """Potential factual or policy contradiction detected between documents."""

    topic: str
    document_a_id: UUID
    document_a_name: str
    document_a_version: int
    document_a_excerpt: str
    document_b_id: UUID
    document_b_name: str
    document_b_version: int
    document_b_excerpt: str
    conflict_summary: str
    remediation_guidance: str


class ConflictReport(BaseModel):
    """Conservative knowledge conflict detection report."""

    knowledge_base_id: UUID
    total_conflicts_detected: int = 0
    items: list[ConflictItem] = []


class DocumentVersionItem(BaseModel):
    """Snapshot of a specific version revision for a document."""

    id: UUID
    document_id: UUID
    version_number: int
    checksum: str
    storage_key: str
    is_active: bool
    chunk_count: int = 0
    created_at: datetime


class DocumentVersionHistoryResponse(BaseModel):
    """Complete version lineage for a document."""

    document_id: UUID
    filename: str
    active_version_number: int
    total_versions: int
    is_fresh: bool = True
    versions: list[DocumentVersionItem] = []


class RepairActionRequest(BaseModel):
    """Targeted repair operation request."""

    action: str = Field(
        ...,
        description="Action to execute: REPAIR_EMBEDDINGS, REGENERATE_CHUNKS, RETRY_EXTRACTION, RECONCILE_STALE, REINDEX_VERSION",
    )
    dry_run: bool = Field(default=False, description="Preview actions without mutating data")


class RepairJobResponse(BaseModel):
    """Execution status and audit trail for a repair operation."""

    job_id: UUID
    knowledge_base_id: UUID
    document_id: UUID | None = None
    action: str
    status: str  # "PENDING" | "RUNNING" | "COMPLETED" | "FAILED"
    dry_run: bool = False
    findings_addressed: list[str] = []
    details: dict[str, object] | None = None
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
