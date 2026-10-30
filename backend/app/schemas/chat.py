"""Pydantic schemas for Phase 6 grounded chat, citation generation, and claim validation."""

import uuid
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.collaboration import CollaborationMeta
from app.schemas.retrieval import RetrievalLatencyBreakdown, RetrievalMode


class ChatResponseStatus(StrEnum):
    """Execution status of grounded chat pipeline."""

    ANSWERED = "answered"
    RECOVERED = "recovered"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    PROVIDER_ERROR = "provider_error"
    RETRIEVAL_ERROR = "retrieval_error"
    TIMED_OUT = "timed_out"
    FAILED = "failed"


class ChatRequest(BaseModel):
    """Payload for authenticated grounded chat query."""

    knowledge_base_id: UUID = Field(..., description="Target Knowledge Base identifier")
    prompt: str = Field(..., min_length=1, max_length=2000, description="User question or query")
    conversation_id: str | None = Field(default=None, description="Optional conversation session identifier")
    mode: RetrievalMode = Field(
        default=RetrievalMode.HYBRID,
        description="Retrieval mode: hybrid (Vector + BM25 with RRF), vector, or lexical",
    )
    enable_reranking: bool = Field(
        default=True,
        description="Whether cross-encoder neural reranking is enabled",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum evidence chunks to retrieve and inject into answer context",
    )

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Prompt cannot be empty or whitespace-only.")
        return v.strip()

    @model_validator(mode="before")
    @classmethod
    def reconcile_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "query" in data and "prompt" not in data:
                data["prompt"] = data["query"]
            elif "message" in data and "prompt" not in data:
                data["prompt"] = data["message"]
        return data


class SourceItem(BaseModel):
    """Document chunk evidence source validated against database metadata."""

    chunk_id: UUID = Field(..., description="Unique document chunk identifier")
    chunkId: UUID | None = Field(default=None, description="CamelCase alias")
    document_id: UUID = Field(..., description="Source document identifier")
    documentId: UUID | None = Field(default=None, description="CamelCase alias")
    document_version_id: UUID | None = Field(default=None, description="Active document version ID")
    documentVersionId: UUID | None = Field(default=None, description="CamelCase alias")
    document_name: str = Field(..., description="Validated original filename of the document")
    documentName: str | None = Field(default=None, description="CamelCase alias")
    chunk_index: int = Field(..., description="Sequential position index in document")
    chunkIndex: int | None = Field(default=None, description="CamelCase alias")
    page_number: int | None = Field(default=None, description="Source page number where available")
    pageNumber: int | None = Field(default=None, description="CamelCase alias")
    section_title: str | None = Field(default=None, description="Structural section heading")
    sectionTitle: str | None = Field(default=None, description="CamelCase alias")
    excerpt: str = Field(..., description="Text excerpt of the source chunk")
    relevance_score: float | None = Field(default=None, description="Retrieval / reranker relevance score")
    relevanceScore: float | None = Field(default=None, description="CamelCase alias")
    is_cited: bool = Field(default=False, description="Whether this source was cited in the generated answer")
    isCited: bool | None = Field(default=None, description="CamelCase alias")

    @model_validator(mode="after")
    def sync_aliases(self) -> "SourceItem":
        if self.chunkId is None:
            self.chunkId = self.chunk_id
        if self.documentId is None:
            self.documentId = self.document_id
        if self.documentVersionId is None:
            self.documentVersionId = self.document_version_id
        if self.documentName is None:
            self.documentName = self.document_name
        if self.chunkIndex is None:
            self.chunkIndex = self.chunk_index
        if self.pageNumber is None:
            self.pageNumber = self.page_number
        if self.sectionTitle is None:
            self.sectionTitle = self.section_title
        if self.relevanceScore is None:
            self.relevanceScore = self.relevance_score
        if self.isCited is None:
            self.isCited = self.is_cited
        return self


class ClaimCitation(BaseModel):
    """Claim-to-evidence attribution mapping an answer claim to supporting chunk IDs."""

    claim_id: str = Field(..., description="Stable claim identifier (e.g. claim-1)")
    claimId: str | None = Field(default=None, description="CamelCase alias")
    text: str = Field(..., description="Specific assertion or claim sentence from the answer")
    source_chunk_ids: list[UUID] = Field(default_factory=list, description="IDs of chunks that support this claim")
    sourceChunkIds: list[UUID] | None = Field(default=None, description="CamelCase alias")

    @model_validator(mode="after")
    def sync_aliases(self) -> "ClaimCitation":
        if self.claimId is None:
            self.claimId = self.claim_id
        if self.sourceChunkIds is None:
            self.sourceChunkIds = self.source_chunk_ids
        return self


class GenerationMeta(BaseModel):
    """Metadata regarding LLM execution."""

    provider: str = Field(..., description="Configured LLM provider used")
    model: str = Field(..., description="LLM model identifier used")
    latency_ms: float = Field(default=0.0, description="Measured generation latency in ms")
    llm_invoked: bool = Field(default=False, description="Whether LLM inference was executed")


class EvidenceMeta(BaseModel):
    """Metadata regarding retrieved evidence and citation validation."""

    retrieved_chunk_count: int = Field(default=0, description="Total chunks retrieved")
    used_source_count: int = Field(default=0, description="Number of distinct sources cited in answer")
    citation_validation_passed: bool = Field(
        default=False, description="Whether all citations in the answer mapped to valid retrieved chunks"
    )
    untrusted_context_truncated: bool = Field(
        default=False, description="Whether retrieved context was truncated due to budget constraints"
    )
    has_relevant_evidence: bool = Field(default=False, description="Whether genuinely relevant evidence was retrieved")


class RecoveryMeta(BaseModel):
    """Metadata regarding Phase 8 self-healing recovery actions and execution diagnostics."""

    recovery_attempted: bool = Field(default=False, description="Whether self-healing recovery was attempted")
    recovery_count: int = Field(default=0, description="Total recovery iterations executed")
    failure_category: str | None = Field(default=None, description="Classified root failure category")
    recovery_action: str | None = Field(default=None, description="Last recovery action executed")
    recovery_outcome: str | None = Field(
        default=None, description="Recovery outcome: recovered, failed, exhausted, non_recoverable"
    )
    rewritten_query: str | None = Field(
        default=None, description="Rewritten search query if query rewriting was applied"
    )
    termination_reason: str | None = Field(default=None, description="Explicit termination reason if stopped")


class ChatCitation(BaseModel):
    """Source provenance citation item for frontend CitationCard rendering."""

    id: int = Field(..., description="1-indexed citation number [1], [2] referenced in generated text")
    chunk_id: UUID = Field(..., description="Unique document chunk identifier")
    chunkId: UUID | None = Field(default=None, description="CamelCase alias for frontend")
    document_id: UUID = Field(..., description="Source document identifier")
    documentId: UUID | None = Field(default=None, description="CamelCase alias for frontend")
    title: str = Field(..., description="Source document original filename")
    section: str | None = Field(default=None, description="Section heading or structural location")
    page: int | None = Field(default=None, description="Page number where chunk appears")
    snippet: str = Field(..., description="Exact textual excerpt used as evidence")
    relevance_score: float | None = Field(default=None, description="Retrieval / reranker relevance score")
    relevanceScore: float | None = Field(default=None, description="CamelCase alias for frontend")

    @model_validator(mode="after")
    def sync_aliases(self) -> "ChatCitation":
        if self.chunkId is None:
            self.chunkId = self.chunk_id
        if self.documentId is None:
            self.documentId = self.document_id
        if self.relevanceScore is None:
            self.relevanceScore = self.relevance_score
        return self


class WorkflowStepEvent(BaseModel):
    """Execution telemetry for a single agent workflow graph node."""

    step_id: str = Field(..., description="Node or step identifier e.g. query_analysis")
    name: str = Field(..., description="Human-readable node label e.g. Query Analysis")
    status: str = Field(default="completed", description="Status: completed, skipped, failed, standby")
    duration_ms: float = Field(default=0.0, description="Measured execution duration in milliseconds")
    description: str | None = Field(default=None, description="Operational detail or decision reason")


class ChatResponse(BaseModel):
    """Full production-grade response payload containing grounded answer and verified citation provenance."""

    id: str = Field(default_factory=lambda: f"m-{uuid.uuid4().hex[:12]}", description="Message identifier")
    role: str = Field(default="assistant", description="Message role")
    content: str = Field(..., description="Grounded AI response text with inline citations")
    answer: str = Field(default="", description="Alias for content matching specification")
    status: ChatResponseStatus = Field(
        default=ChatResponseStatus.ANSWERED,
        description="Pipeline execution status: answered, insufficient_evidence, provider_error, retrieval_error",
    )
    timestamp: str = Field(..., description="Response generation timestamp")
    knowledge_base_id: UUID = Field(..., description="Knowledge Base identifier queried")
    conversation_id: str | None = Field(default=None, description="Conversation session identifier")

    # Structured Citation & Provenance Breakdown
    sources: list[SourceItem] = Field(default_factory=list, description="Validated source items from database metadata")
    claim_citations: list[ClaimCitation] = Field(default_factory=list, description="Claim-to-evidence mappings")
    citations: list[ChatCitation] = Field(
        default_factory=list, description="Active citation items referenced in answer"
    )

    # Operational Telemetry & Meta
    generation: GenerationMeta | None = Field(default=None, description="LLM generation telemetry")
    evidence: EvidenceMeta | None = Field(default=None, description="Evidence usage and validation metadata")
    recovery: RecoveryMeta | None = Field(default=None, description="Self-healing recovery telemetry")

    confidence: float | None = Field(
        default=None,
        description="Calibrated confidence score if verified; None if uncalibrated/unverified",
    )
    verification_status: str = Field(
        default="grounded_evidence",
        description="Status of verification guardrail: 'grounded_evidence', 'general_ai_answer', 'insufficient_evidence', or 'unverified'",
    )
    answer_type: str = Field(
        default="document_grounded",
        description="Classification: 'document_grounded', 'general_ai', 'insufficient_evidence', or 'provider_error'",
    )
    answerType: str | None = Field(default=None, description="CamelCase alias for frontend")
    is_insufficient_evidence: bool = Field(
        default=False,
        description="True if retrieval returned no relevant context or LLM reported insufficient evidence",
    )
    retrieval_latency: RetrievalLatencyBreakdown | None = Field(
        default=None,
        description="Measured latency breakdown for retrieval stages (in ms)",
    )
    generation_ms: float = Field(default=0.0, description="Measured response generation latency (in ms)")
    total_ms: float = Field(default=0.0, description="Total end-to-end request latency (in ms)")
    model: str = Field(default="", description="LLM model used for synthesis")
    tokens_used: int | None = Field(default=None, description="Total tokens consumed if reported by provider")
    retry_count: int = Field(default=0, description="Number of bounded retrieval retries executed")
    trace_id: str | None = Field(default=None, description="Correlated Phase 10 execution trace identifier")
    traceId: str | None = Field(default=None, description="CamelCase alias for frontend")
    workflow_steps: list[WorkflowStepEvent] = Field(
        default_factory=list, description="Executed LangGraph workflow step events with measured latencies"
    )
    collaboration: CollaborationMeta | None = Field(
        default=None, description="Multi-agent collaboration metadata across specialized roles"
    )

    @model_validator(mode="after")
    def sync_answer_alias(self) -> "ChatResponse":
        if not self.answer and self.content:
            self.answer = self.content
        elif not self.content and self.answer:
            self.content = self.answer
        if self.traceId is None:
            self.traceId = self.trace_id
        if self.trace_id is None:
            self.trace_id = self.traceId
        if self.answerType is None:
            self.answerType = self.answer_type
        if self.answer_type is None:
            self.answer_type = self.answerType or "document_grounded"
        return self
