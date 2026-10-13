# System Architecture — Self-Healing RAG Agent

## 1. Architectural Philosophy

The Self-Healing RAG Agent platform is built upon **Domain-Driven Design (DDD)** and **Clean Onion Architecture**. The system decouples high-level business capabilities from low-level infrastructure drivers (such as LLM APIs, vector databases, cache engines, and database protocols).

```
   ┌────────────────────────────────────────────────────────┐
   │                     Presentation                       │
   │           (React 19 + Vite + Tailwind CSS)             │
   └───────────────────────────┬────────────────────────────┘
                               │ HTTP / JSON (Correlation ID)
   ┌───────────────────────────▼────────────────────────────┐
   │                       API Layer                        │
   │               (FastAPI /api/v1/ Routers)               │
   └───────────────────────────┬────────────────────────────┘
                               │ Dependency Injection
   ┌───────────────────────────▼────────────────────────────┐
   │               Application / Service Layer              │
   │       (HealthService, SystemService, Workflow Coord)   │
   └───────────────────────────┬────────────────────────────┘
                               │
   ┌───────────────────────────▼────────────────────────────┐
   │                     Domain Layer                       │
   │         (Interfaces: LLM, Embeddings, VectorStore)     │
   └───────────────────────────┬────────────────────────────┘
                               │ Implementations
   ┌───────────────────────────▼────────────────────────────┐
   │                 Infrastructure Layer                   │
   │   (SQLAlchemy 2.0 Async, RedisClient, pgvector, HTTPX) │
   └────────────────────────────────────────────────────────┘
```

## 2. Key Layer Responsibilities

### Presentation Layer (`frontend/`)
- Pure client-side SPA written in TypeScript with React 19 and Vite.
- TanStack Query manages asynchronous server state, automated retries, and polling intervals.
- Lucide React and custom Tailwind v4 utility styles deliver a high-contrast enterprise dark UI.
- All routes and components respect strict encapsulation. No AI logic or provider secrets reside in the client.

### API Layer (`backend/app/api/`)
- Route definitions grouped under semantic `/api/v1/` prefixes.
- Zero business logic inside route controllers. Route functions validate request schemas, inject services, invoke operations, and return typed envelopes.
- Correlation IDs (`X-Request-ID`) generated or preserved on every request.

### Service Layer (`backend/app/services/`)
- Orchestrates multi-step application use cases.
- Aggregates domain models and repository queries without knowing specific database or HTTP transport details.

### Domain Layer (`backend/app/domain/`)
- Contains enterprise abstractions:
  - `LLMProviderInterface`: Supports hot-swapping between OpenAI, Anthropic, and local LLMs (Ollama/vLLM).
  - `EmbeddingProviderInterface`: Enforces uniform document and query embedding contracts.
  - `VectorStoreInterface`: Decouples vector indexing operations from underlying storage (pgvector, Qdrant).
  - `RerankerInterface`: Abstract cross-encoder reranking contract.
  - `ObjectStorageInterface`: S3/MinIO file handling abstraction.
  - `ObservabilityInterface`: Abstract distributed tracing and metric emission.

### Infrastructure Layer (`backend/app/infrastructure/`)
- Concrete database session management via SQLAlchemy 2.0 Async (`create_async_engine`, `async_sessionmaker`).
- Distributed caching and Redis async connection pooling (`redis.asyncio`).
- Audit logging repository and migrations.

## 3. Technology Selection Rationale

| Component | Selected Technology | Technical Rationale |
| :--- | :--- | :--- |
| **Backend Runtime** | Python 3.11+ / 3.13 | Native async/await support, first-class AI library ecosystem, and type annotation maturity. |
| **Web Framework** | FastAPI 0.115+ | High throughput Starlette ASGI core, automatic OpenAPI 3.1 schema generation, and Pydantic v2 validation. |
| **ORM / Data Access** | SQLAlchemy 2.0 (Async) | Strict 2.0 declarative syntax, connection pool tuning, and complete asyncpg compatibility. |
| **Vector Engine** | PostgreSQL + pgvector | Eliminates polyglot persistence overhead for early-to-mid scale; ACID transactional guarantees joinable with relational audit logs. |
| **Cache & State** | Redis 7 | Sub-millisecond latency for session coordination, rate-limiting tokens, and agent checkpointing. |
| **Frontend Framework** | React 19 + TypeScript | Component predictability, ecosystem maturity, and strict compile-time type verification. |
| **Bundler & Tooling** | Vite + Tailwind CSS v4 | Sub-second HMR startup, minimal bundle footprint, and robust CSS variable theming. |

## 4. Phase 5 Hybrid Retrieval Engine Architecture

### Pipeline Flow
```
User Query
    │
    ▼
[Authorization & Ownership Check] (User owns requested Knowledge Base)
    │
    ▼
[Input Validation] (Non-empty, non-whitespace, bounded top_k / candidate_limit)
    │
    ├───────────────────────────────────────────────┐
    ▼                                               ▼
[Semantic Vector Search]                    [BM25 Lexical Search]
- FastEmbed BAAI/bge-small-en-v1.5 (384-d)    - BM25Plus algorithm
- Vector validation (dimension, finiteness)  - Custom technical tokenizer
- Application-side Cosine Similarity         - Document length normalization
- Tenant-scoped to authorized KB & ver       - Tenant-scoped to authorized KB & ver
    │                                               │
    └───────────────────────┬───────────────────────┘
                            ▼
           [Reciprocal Rank Fusion (RRF)]
           - Formula: RRF(d) = Σ 1 / (k + rank_i(d)), k=60
           - Deduplication by chunk ID
           - Provenance tracking (hybrid, vector, lexical)
           - Deterministic tie-breaking
                            │
                            ▼
           [Neural Cross-Encoder Reranking]
           - FlashRank ms-marco-TinyBERT-L-2-v2 (~3.26MB, ONNX CPU)
           - Cached singleton instance
           - Graceful fallback with diagnostic warnings
                            │
                            ▼
                [Final Ranked Top-K Chunks]
                - Transparent multi-stage scoring audit trail
                - Latency breakdown (vector, lexical, fusion, rerank, total)
```

### JSON Embedding Storage & pgvector Migration Path
- **Current State**: Embeddings in `document_chunks.embedding` are stored as JSON arrays (`[float, ...]`) and loaded via `ResilientVector(384)`.
- **Application-Side Cosine Similarity**: Scoped strictly by `knowledge_base_id` and `owner_id`. Zero-vectors and non-finite vectors are rejected or safely filtered.
- **Scaling Limit**: Suitable for small-to-medium corpora (< 100,000 chunks per knowledge base).
- **Future Native pgvector Migration**:
  1. Add migration to alter column `embedding` type to `vector(384) USING embedding::text::vector(384)`.
  2. Create HNSW index: `CREATE INDEX ix_document_chunks_embedding_hnsw ON document_chunks USING hnsw (embedding vector_cosine_ops);`.
  3. Swap `VectorRetriever` query to use SQLAlchemy pgvector distance operator `<=>` (cosine distance).

