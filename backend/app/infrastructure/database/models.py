"""SQLAlchemy 2.0 ORM entity definitions.

Includes foundational AuditLog model for Phase 1 observability and system health,
with typed model structures prepared for future entity expansions:
- User
- Workspace
- Document
- DocumentChunk
- Conversation
- Message
- Query
- RetrievalResult
- AgentRun
- EvaluationRun
- AuditLog
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.infrastructure.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship


class ResilientVector(Vector):
    """Vector column type that processes both native pgvector string format and JSON list format."""

    cache_ok = True

    def result_processor(self, dialect: Any, coltype: Any) -> Any:
        base_proc = super().result_processor(dialect, coltype)

        def process(value: Any) -> list[float] | None:
            if value is None:
                return None
            if isinstance(value, list):
                return [float(x) for x in value]
            res = base_proc(value)
            return [float(x) for x in res] if res is not None else None

        return process


class UserRole(StrEnum):
    """Role-based access control roles."""

    USER = "USER"
    ADMIN = "ADMIN"
    # Future extension points:
    # DEVELOPER = "DEVELOPER"
    # ANALYST = "ANALYST"
    # OWNER = "OWNER"


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """User entity for authentication, identity, and resource ownership."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default=UserRole.USER.value, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    sessions: Mapped[list["UserSession"]] = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )
    knowledge_bases: Mapped[list["KnowledgeBase"]] = relationship(
        "KnowledgeBase",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="select",
    )
    evaluation_runs: Mapped[list["EvaluationRun"]] = relationship(
        "EvaluationRun",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )
    traces: Mapped[list["ExecutionTrace"]] = relationship(
        "ExecutionTrace",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )

    __table_args__ = (Index("ix_users_email_active", "email", "is_active"),)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"


class UserSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """User session and refresh token storage with rotation and revocation."""

    __tablename__ = "user_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    token_family: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # Relationship back to User
    user: Mapped["User"] = relationship("User", back_populates="sessions", lazy="joined")

    __table_args__ = (
        Index("ix_user_sessions_user_expires", "user_id", "expires_at"),
        Index("ix_user_sessions_family", "token_family"),
    )

    def __repr__(self) -> str:
        return f"<UserSession id={self.id} user_id={self.user_id} revoked={self.revoked_at is not None}>"


class AuditLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """System and security audit log entity."""

    __tablename__ = "audit_logs"

    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    actor_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="success")
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    __table_args__ = (Index("ix_audit_logs_action_created", "action", "created_at"),)

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} action={self.action} status={self.status}>"


# ==============================================================================
# Phase 4: Knowledge Base, Documents, Versions, Chunks & Vector Embeddings
# ==============================================================================


class KnowledgeBaseStatus(StrEnum):
    """Knowledge Base lifecycle status."""

    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class KnowledgeBase(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Knowledge Base collection entity owned by an authenticated user."""

    __tablename__ = "knowledge_bases"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default=KnowledgeBaseStatus.ACTIVE.value, nullable=False, index=True
    )

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="knowledge_bases", lazy="select")
    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (Index("ix_knowledge_bases_owner_status", "owner_id", "status"),)

    def __repr__(self) -> str:
        return f"<KnowledgeBase id={self.id} name={self.name} owner_id={self.owner_id}>"


class DocumentStatus(StrEnum):
    """Document ingestion lifecycle status."""

    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"
    OCR_REQUIRED = "OCR_REQUIRED"
    DELETED = "DELETED"


class Document(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Document entity tracking uploaded files, metadata, and ingestion lifecycle."""

    __tablename__ = "documents"

    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # SHA-256
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=DocumentStatus.UPLOADED.value, nullable=False, index=True)
    ingestion_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    document_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    knowledge_base: Mapped["KnowledgeBase"] = relationship("KnowledgeBase", back_populates="documents", lazy="joined")
    versions: Mapped[list["DocumentVersion"]] = relationship(
        "DocumentVersion",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_documents_kb_checksum", "knowledge_base_id", "checksum"),
        Index("ix_documents_kb_status", "knowledge_base_id", "status"),
        Index("ix_documents_owner_kb", "owner_id", "knowledge_base_id"),
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} filename={self.filename} status={self.status}>"


class DocumentVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Document versioning snapshot tracking file revisions and active chunk sets."""

    __tablename__ = "document_versions"

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="versions", lazy="joined")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="version",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (Index("ix_document_versions_doc_ver", "document_id", "version_number"),)

    def __repr__(self) -> str:
        return f"<DocumentVersion id={self.id} document_id={self.document_id} ver={self.version_number}>"


class DocumentChunk(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Semantic chunk partition of a document storing clean content, citation metadata, and dense vector embedding."""

    __tablename__ = "document_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Embedding model tracking
    embedding_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="fastembed")
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False, default="BAAI/bge-small-en-v1.5")
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False, default=384)
    embedding_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Dense Vector Column for PostgreSQL pgvector / resilient storage (dimension 384)
    embedding: Mapped[list[float] | None] = mapped_column(ResilientVector(384), nullable=True)

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="chunks", lazy="joined")
    version: Mapped["DocumentVersion"] = relationship("DocumentVersion", back_populates="chunks", lazy="joined")

    __table_args__ = (
        Index("ix_document_chunks_doc_chunk_idx", "document_id", "chunk_index"),
        Index("ix_document_chunks_version", "document_version_id"),
    )

    def __repr__(self) -> str:
        return f"<DocumentChunk id={self.id} doc_id={self.document_id} idx={self.chunk_index}>"


class EvaluationRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Stores full benchmark run metadata and quality summary scores for Phase 9."""

    __tablename__ = "evaluation_runs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="completed", nullable=False)
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pass_rate: Mapped[float] = mapped_column(nullable=False, default=0.0)

    # Serialized aggregate metrics and configuration
    summary_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    run_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="evaluation_runs", lazy="joined")
    case_results: Mapped[list["EvaluationCaseResultRecord"]] = relationship(
        "EvaluationCaseResultRecord",
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_evaluation_runs_user_status", "user_id", "status"),
        Index("ix_evaluation_runs_dataset", "dataset_name", "dataset_version"),
    )

    def __repr__(self) -> str:
        return f"<EvaluationRun id={self.id} name={self.name} pass_rate={self.pass_rate:.1%}>"


class EvaluationCaseResultRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Case-level execution result with individual retrieval, grounding, and recovery scores."""

    __tablename__ = "evaluation_case_results"

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    test_case_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="passed")
    query: Mapped[str] = mapped_column(Text, nullable=False)

    # JSON metrics dictionaries
    retrieval_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    answer_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    recovery_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    failure_reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    total_latency_ms: Mapped[float] = mapped_column(nullable=False, default=0.0)
    actual_response_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    run: Mapped["EvaluationRun"] = relationship("EvaluationRun", back_populates="case_results", lazy="joined")

    __table_args__ = (Index("ix_case_results_run_category", "run_id", "category"),)

    def __repr__(self) -> str:
        return f"<EvaluationCaseResultRecord id={self.id} case={self.test_case_id} passed={self.passed}>"


class ExecutionTrace(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """End-to-end distributed execution trace for RAG requests and agent workflows."""

    __tablename__ = "execution_traces"

    trace_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    knowledge_base_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="completed", index=True)
    duration_ms: Mapped[float] = mapped_column(nullable=False, default=0.0)
    tokens_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    estimated_cost_usd: Mapped[float | None] = mapped_column(nullable=True)
    cost_status: Mapped[str | None] = mapped_column(String(50), nullable=True, default="unavailable")
    cost_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    pricing_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    recovery_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retrieval_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    retrieval_scores: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    evidence_sufficiency: Mapped[str | None] = mapped_column(String(50), nullable=True)
    citation_validation_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    verification_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    trace_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    user: Mapped["User | None"] = relationship("User", back_populates="traces", lazy="select")
    spans: Mapped[list["TraceSpanRecord"]] = relationship(
        "TraceSpanRecord",
        back_populates="trace",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_execution_traces_user_status", "user_id", "status"),
        Index("ix_execution_traces_status_created", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ExecutionTrace id={self.id} trace_id={self.trace_id} status={self.status} duration_ms={self.duration_ms}>"


class TraceSpanRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Granular execution span within an ExecutionTrace recording entry, duration, and outcomes."""

    __tablename__ = "trace_spans"

    trace_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("execution_traces.trace_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    span_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    parent_span_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    step_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    duration_ms: Mapped[float] = mapped_column(nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="completed")
    inputs: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    outputs: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(nullable=True)
    is_skipped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    span_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    trace: Mapped["ExecutionTrace"] = relationship("ExecutionTrace", back_populates="spans", lazy="joined")

    __table_args__ = (Index("ix_trace_spans_trace_step", "trace_id", "step_type"),)

    def __repr__(self) -> str:
        return f"<TraceSpanRecord id={self.id} span_id={self.span_id} name={self.name} duration_ms={self.duration_ms}>"


# ==============================================================================
# Phase 12: Knowledge Base Management & Repair Jobs
# ==============================================================================


class KnowledgeBaseRepairJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tracks asynchronous and synchronous knowledge base and document repair jobs."""

    __tablename__ = "kb_repair_jobs"

    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False, index=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    findings_addressed: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_kb_repair_jobs_kb_status", "knowledge_base_id", "status"),
        Index("ix_kb_repair_jobs_doc_status", "document_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<KnowledgeBaseRepairJob id={self.id} action={self.action} status={self.status} dry_run={self.dry_run}>"


# ==============================================================================
# Phase 13: Data Sources & Connected Ingestion Integrations
# ==============================================================================


class DataSourceType(StrEnum):
    LOCAL = "local"
    WEB = "web"
    GITHUB = "github"
    GDRIVE = "gdrive"
    NOTION = "notion"
    POSTGRES = "postgres"


class DataSourceStatus(StrEnum):
    NOT_CONFIGURED = "not_configured"
    SETUP_REQUIRED = "setup_required"
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    SYNCING = "syncing"
    READY = "ready"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"


class DataSource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """External connected data source integrated with knowledge corpus."""

    __tablename__ = "data_sources"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    knowledge_base_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        String(50), default=DataSourceStatus.NOT_CONFIGURED.value, nullable=False, index=True
    )
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_sync_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    synced_documents_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    synced_chunks_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", lazy="select")
    knowledge_base: Mapped["KnowledgeBase | None"] = relationship("KnowledgeBase", lazy="select")

    __table_args__ = (Index("ix_data_sources_user_type", "user_id", "source_type"),)

    def __repr__(self) -> str:
        return f"<DataSource id={self.id} type={self.source_type} name={self.name} status={self.status}>"
