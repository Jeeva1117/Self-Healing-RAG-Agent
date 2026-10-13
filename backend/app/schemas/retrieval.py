"""Pydantic schemas for Phase 5 Hybrid Retrieval, RRF Fusion, and Cross-Encoder Reranking."""

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class RetrievalMode(StrEnum):
    """Supported retrieval execution modes."""

    HYBRID = "hybrid"
    VECTOR = "vector"
    LEXICAL = "lexical"


class RetrievalRequest(BaseModel):
    """Request payload for hybrid, vector, or lexical document retrieval."""

    knowledge_base_id: UUID = Field(..., description="Target Knowledge Base identifier")
    query: str = Field(..., min_length=1, max_length=1000, description="Natural language search query")
    mode: RetrievalMode = Field(
        default=RetrievalMode.HYBRID,
        description="Retrieval strategy: hybrid (Vector + BM25 with RRF), vector (semantic), or lexical (BM25)",
    )
    retrieval_mode: RetrievalMode | None = Field(
        default=None,
        description="Alias for mode parameter",
    )
    enable_reranking: bool = Field(
        default=True,
        description="Whether to execute cross-encoder neural reranking on top fused candidates",
    )
    reranking_required: bool = Field(
        default=False,
        description="If True and reranking fails, aborts request with error instead of graceful fallback to RRF",
    )
    candidate_limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum candidates retrieved per retriever before fusion",
    )
    candidate_k: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Alias for candidate_limit parameter",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of final top ranked results to return",
    )
    similarity_threshold: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum vector similarity cutoff threshold",
    )
    rrf_k: int = Field(
        default=60,
        ge=1,
        le=200,
        description="Reciprocal Rank Fusion smoothing constant k (standard default: 60)",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Query cannot be empty or whitespace-only.")
        return v.strip()

    @model_validator(mode="before")
    @classmethod
    def reconcile_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "retrieval_mode" in data and data["retrieval_mode"] is not None and "mode" not in data:
                data["mode"] = data["retrieval_mode"]
            elif "mode" in data and "retrieval_mode" not in data:
                data["retrieval_mode"] = data["mode"]

            if "candidate_k" in data and data["candidate_k"] is not None and "candidate_limit" not in data:
                data["candidate_limit"] = data["candidate_k"]
            elif "candidate_limit" in data and "candidate_k" not in data:
                data["candidate_k"] = data["candidate_limit"]
        return data


class KBSearchBody(BaseModel):
    """Payload for POST /api/v1/knowledge-bases/{id}/search where knowledge_base_id is in URL path."""

    query: str = Field(..., min_length=1, max_length=1000, description="Natural language search query")
    top_k: int = Field(default=5, ge=1, le=50, description="Number of final top ranked results to return")
    candidate_limit: int = Field(default=20, ge=1, le=100, description="Maximum candidates retrieved per retriever")
    candidate_k: int | None = Field(default=None, ge=1, le=100, description="Alias for candidate_limit")
    mode: RetrievalMode = Field(default=RetrievalMode.HYBRID, description="Retrieval mode")
    retrieval_mode: RetrievalMode | None = Field(default=None, description="Alias for mode")
    enable_reranking: bool = Field(default=True, description="Whether to execute neural reranking")
    reranking_required: bool = Field(default=False, description="Strict reranker enforcement")
    similarity_threshold: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum similarity cutoff")
    rrf_k: int = Field(default=60, ge=1, le=200, description="RRF smoothing constant k")

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Query cannot be empty or whitespace-only.")
        return v.strip()

    @model_validator(mode="before")
    @classmethod
    def reconcile_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "retrieval_mode" in data and data["retrieval_mode"] is not None and "mode" not in data:
                data["mode"] = data["retrieval_mode"]
            if "candidate_k" in data and data["candidate_k"] is not None and "candidate_limit" not in data:
                data["candidate_limit"] = data["candidate_k"]
        return data


class RetrievalResultItem(BaseModel):
    """A retrieved document chunk with source provenance and transparent score audit trail."""

    chunk_id: UUID = Field(..., description="Primary identifier of the document chunk")
    document_id: UUID = Field(..., description="Parent document identifier")
    document_version_id: UUID | None = Field(default=None, description="Active document version identifier")
    document_name: str = Field(..., description="Original filename of the source document")
    content: str = Field(..., description="Extractable chunk text snippet")
    page_number: int | None = Field(default=None, description="Source page number where available")
    section_title: str | None = Field(default=None, description="Extracted structural section or heading")
    chunk_index: int = Field(..., description="Sequential position index in the document")
    token_count: int | None = Field(default=None, description="Number of tokens in chunk")
    character_count: int = Field(..., description="Number of characters in chunk")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Custom citation and chunk metadata")

    # Multi-stage Scoring Audit Trail (both vector_* / semantic_* and lexical_* / bm25_* supported)
    vector_rank: int | None = Field(default=None, description="Rank from semantic vector search (1-indexed)")
    vector_score: float | None = Field(default=None, description="Cosine similarity score from vector search [0..1]")
    semantic_rank: int | None = Field(default=None, description="Alias for vector_rank")
    semantic_score: float | None = Field(default=None, description="Alias for vector_score")

    lexical_rank: int | None = Field(default=None, description="Rank from BM25 lexical search (1-indexed)")
    lexical_score: float | None = Field(default=None, description="Raw BM25 Okapi lexical relevance score")
    keyword_rank: int | None = Field(default=None, description="Alias for lexical_rank")
    bm25_score: float | None = Field(default=None, description="Alias for lexical_score")

    rrf_rank: int | None = Field(default=None, description="Rank after Reciprocal Rank Fusion")
    rrf_score: float | None = Field(default=None, description="Computed Reciprocal Rank Fusion score: sum(1/(k+rank))")

    reranker_rank: int | None = Field(default=None, description="Rank after Cross-Encoder reranking")
    reranker_score: float | None = Field(
        default=None, description="Cross-encoder relevance probability score from neural reranker [0..1]"
    )
    rerank_score: float | None = Field(default=None, description="Alias for reranker_score")

    final_rank: int = Field(..., description="Final sequential position in returned result set (1-indexed)")
    stage_provenance: str = Field(
        ...,
        description="Stage origin: 'hybrid' (present in both), 'vector' (semantic only), or 'lexical' (BM25 only)",
    )

    @model_validator(mode="after")
    def sync_score_aliases(self) -> "RetrievalResultItem":
        if self.semantic_rank is None:
            self.semantic_rank = self.vector_rank
        if self.vector_rank is None:
            self.vector_rank = self.semantic_rank

        if self.semantic_score is None:
            self.semantic_score = self.vector_score
        if self.vector_score is None:
            self.vector_score = self.semantic_score

        if self.keyword_rank is None:
            self.keyword_rank = self.lexical_rank
        if self.lexical_rank is None:
            self.lexical_rank = self.keyword_rank

        if self.bm25_score is None:
            self.bm25_score = self.lexical_score
        if self.lexical_score is None:
            self.lexical_score = self.bm25_score

        if self.rerank_score is None:
            self.rerank_score = self.reranker_score
        if self.reranker_score is None:
            self.reranker_score = self.rerank_score

        return self


class RetrievalLatencyBreakdown(BaseModel):
    """High-resolution measurement of latency across retrieval pipeline stages (in milliseconds)."""

    vector_ms: float = Field(default=0.0, description="Dense embedding generation and vector search time")
    lexical_ms: float = Field(default=0.0, description="BM25 tokenization and lexical retrieval time")
    fusion_ms: float = Field(default=0.0, description="Reciprocal Rank Fusion time")
    rerank_ms: float = Field(default=0.0, description="Cross-encoder neural reranking time")
    total_ms: float = Field(default=0.0, description="Total end-to-end retrieval execution time")


class RetrievalResponse(BaseModel):
    """Envelope response containing ranked results and operational diagnostics."""

    query: str = Field(..., description="Normalized search query")
    knowledge_base_id: UUID = Field(..., description="Searched Knowledge Base ID")
    mode: str = Field(..., description="Retrieval mode executed")
    retrieval_mode: str = Field(default="", description="Alias for mode")
    enable_reranking: bool = Field(..., description="Whether reranking was enabled")
    reranking_enabled: bool = Field(default=True, description="Alias for enable_reranking")
    reranking_applied: bool = Field(default=False, description="Whether neural reranking was successfully executed")
    candidate_count: int = Field(..., description="Total candidate chunks retrieved before final cutoff")
    returned_count: int = Field(..., description="Number of results returned in this response")
    total_results: int = Field(default=0, description="Alias for returned_count")
    results: list[RetrievalResultItem] = Field(default_factory=list, description="Ranked retrieved chunks")
    latency: RetrievalLatencyBreakdown = Field(..., description="Pipeline execution latency breakdown")
    latency_ms: float = Field(default=0.0, description="Total execution latency in milliseconds")
    warnings: list[str] = Field(default_factory=list, description="Safe retrieval diagnostics and warnings")

    @model_validator(mode="after")
    def sync_response_fields(self) -> "RetrievalResponse":
        if not self.retrieval_mode:
            self.retrieval_mode = self.mode
        self.reranking_enabled = self.enable_reranking
        if self.total_results == 0 and self.returned_count > 0:
            self.total_results = self.returned_count
        elif self.returned_count == 0 and self.total_results > 0:
            self.returned_count = self.total_results
        if self.latency_ms == 0.0 and self.latency.total_ms > 0:
            self.latency_ms = self.latency.total_ms
        return self


class ComparisonResponse(BaseModel):
    """Comparison view payload returning Vector, Lexical, and Hybrid results side-by-side."""

    query: str
    knowledge_base_id: UUID
    vector_results: list[RetrievalResultItem]
    lexical_results: list[RetrievalResultItem]
    hybrid_results: list[RetrievalResultItem]
    latency: RetrievalLatencyBreakdown
    warnings: list[str] = Field(default_factory=list)

