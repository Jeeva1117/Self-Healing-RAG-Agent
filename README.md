# Self-Healing RAG Agent

<div align="center">

**Building More Reliable Retrieval-Augmented Generation with Intelligent Recovery and Evaluation.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11%20%7C%203.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI: 0.115+](https://img.shields.io/badge/Backend-FastAPI%200.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React: 19](https://img.shields.io/badge/Frontend-React%2019%20%2B%20TypeScript-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Vector: pgvector](https://img.shields.io/badge/Vector%20Store-pgvector%20384d-336791?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Embeddings: FastEmbed](https://img.shields.io/badge/Embeddings-FastEmbed%20(BGE--small)-FF6F00)](https://github.com/qdrant/fastembed)
[![Reranker: FlashRank](https://img.shields.io/badge/Reranker-FlashRank%20ONNX-2E7D32)](https://github.com/PrithivirajDamodaran/FlashRank)
[![CI: Passing](https://img.shields.io/badge/CI-Passing-brightgreen?logo=github-actions&logoColor=white)](.github/workflows/ci.yml)
[![Tests: 321 Passing](https://img.shields.io/badge/Tests-321%20Passed%20(100%25)-brightgreen)](docs/development.md)

[Architecture](#system-architecture) • [Key Features](#key-features) • [RAG Pipeline](#end-to-end-ai--rag-pipeline) • [Self-Healing Engine](#self-healing--recovery-mechanism) • [API Catalog](#rest-api-catalog) • [Getting Started](#local-development-setup)

</div>

---

## Table of Contents

- [1. Executive Overview](#1-executive-overview)
- [2. The Fragility of Traditional RAG](#2-the-fragility-of-traditional-rag)
- [3. Key Features](#3-key-features)
- [4. System Architecture](#4-system-architecture)
- [5. Technology Stack](#5-technology-stack)
- [6. Project Directory Structure](#6-project-directory-structure)
- [7. End-to-End AI & RAG Pipeline](#7-end-to-end-ai--rag-pipeline)
- [8. Self-Healing & Recovery Mechanism](#8-self-healing--recovery-mechanism)
- [9. Multi-Agent Collaboration Engine](#9-multi-agent-collaboration-engine)
- [10. Evaluation & Observability Intelligence](#10-evaluation--observability-intelligence)
- [11. REST API Catalog](#11-rest-api-catalog)
- [12. Database Schema & Persistence](#12-database-schema--persistence)
- [13. Security, Governance & Isolation](#13-security-governance--isolation)
- [14. Local Development Setup](#14-local-development-setup)
- [15. Environment Configuration](#15-environment-configuration)
- [16. Docker & Container Deployment](#16-docker--container-deployment)
- [17. Testing & Quality Assurance](#17-testing--quality-assurance)
- [18. Roadmap & Known Limitations](#18-roadmap--known-limitations)
- [19. Contributing & License](#19-contributing--license)

---

## 1. Executive Overview

The **Self-Healing RAG Agent** is an enterprise-grade retrieval-augmented generation and autonomous knowledge management platform designed to eliminate the inherent unreliability of naive, one-way RAG pipelines.

Production RAG systems frequently suffer from silent degradation: queries return irrelevant chunks, small corpus changes corrupt embeddings, language models invent citations, and temporary service dropouts cause catastrophic request failures. 

Rather than treating RAG as an open-loop sequence (User → Search → Prompt → LLM), this platform introduces a **cyclic, verifiable agentic graph**:
1. **Validates Evidence First**: Inspects retrieved chunks for coverage, freshness, and relevance before generating answers.
2. **Detects & Classifies Failures**: Identifies 7 granular failure modes (retrieval dropouts, low relevance, insufficient evidence, hallucination, bad citations, etc.).
3. **Applies Bounded Self-Healing**: Triggers deterministic recovery actions (adaptive query rewriting, candidate limit expansion, BM25/vector strategy fallbacks, prompt constraint tightening) within strict attempt budgets.
4. **Enforces Grounded Citations**: Verifies every claim against retrieved evidence and returns interactive, sentence-level source citations (`[1]`, `[2]`).
5. **Continuous Reliability Monitoring**: Captures distributed waterfall spans, computes token cost attribution, audits health gaps, and evaluates retrieval benchmarks (Precision@K, Recall@K, MRR, nDCG@K).

---

## 2. The Fragility of Traditional RAG

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Traditional Naive RAG                           │
│                                                                        │
│  User Query ──► Naive Search ──► Blind Context ──► LLM Hallucination   │
│                      ▲                                   │             │
│                      └────── No Feedback Loop ───────────┘             │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│                      Self-Healing RAG Agent                            │
│                                                                        │
│  User Query ──► Hybrid Search ──► Assessment ──► Verification Shield   │
│                      ▲                 │                 │             │
│                      └── Self-Healing ◄┴── Bounded Retry ◄┘             │
│                          Engine (Rewriting / Fallback / Expansion)     │
└────────────────────────────────────────────────────────────────────────┘
```

Traditional deployments consistently break down in five major enterprise scenarios:

1. **Vocabulary Mismatch & Semantic Drift**: Semantic vector embeddings miss exact serial numbers, acronyms, or SKU codes, while pure keyword search misses conceptual synonyms.
2. **Context Fragmentation**: Static chunking boundaries sever crucial relationships across tables, lists, and multi-paragraph statements.
3. **Ungrounded Hallucinations**: LLMs fill factual gaps with plausible-sounding fabrications rather than admitting evidence insufficiency.
4. **Silent Ingestion & Index Corruption**: Workers crash mid-chunking, leaving corrupted vectors, stale checksums, or orphaned records with zero health visibility.
5. **Lack of Operational Telemetry**: Teams operate with blind spots regarding end-to-end latency, token consumption costs, model drift, and failure rates.

---

## 3. Key Features

- 📂 **Multi-Format Ingestion Engine**: Native parsers for 9 document extensions: PDF, DOCX, TXT, Markdown, CSV, HTML, JSON, and XLSX with structured metadata extraction.
- 🔍 **Hybrid Fusion Retrieval**: Dual-retriever pipeline combining dense semantic vector search (`pgvector` with 384-dimensional BGE embeddings) and sparse lexical search (`rank-bm25`), fused via **Reciprocal Rank Fusion (RRF, $k=60$)**.
- ⚡ **Local Neural Reranking**: Ultra-fast ONNX cross-encoder reranking powered by **FlashRank** (`ms-marco-TinyBERT-L-2-v2`) executed entirely on CPU with zero external API calls.
- 🛡️ **Evidence-Grounded Synthesis & Verification**: Produces strictly grounded answers with verifiable bracketed sentence citations (`[1]`, `[2]`). If evidence is insufficient, the system gracefully admits it instead of fabricating answers.
- 🔄 **Bounded Self-Healing Engine**: Diagnoses pipeline errors into a 7-part failure taxonomy and applies 8 targeted recovery policies with strict execution deadlines and cycle-prevention guards.
- 🤖 **LangGraph Agentic Orchestration**: Stateful 10-node decision graph featuring conditional routing, dynamic query decomposition, evidence assessment, and self-correction loops.
- 👥 **Multi-Agent Collaboration**: Specialized collaborative workflow distributing subtasks across Coordinator, Retrieval Specialist, Fact-Checker, and Synthesis agents.
- 📊 **Empirical Evaluation Suite**: Built-in benchmark harness calculating Precision@K, Recall@K, Mean Reciprocal Rank (MRR), nDCG@K, Key Fact Coverage, and Groundedness.
- 📈 **Full-Stack Observability & Error Explorer**: Distributed waterfall tracing, token and dollar cost tracking per model, reliability alerting, and structured root-cause recommendations.
- 🔌 **Enterprise Data Source Connectors**: Out-of-the-box connectors for GitHub repositories, PostgreSQL databases, web scrapers, Google Drive, and Notion with credential masking.
- 🔐 **Zero-Trust Security & Multi-Tenancy**: Tenant-isolated knowledge bases, Argon2id password encryption, short-lived JWT access tokens, rotated refresh token families, and automated secret redaction in logs.
- 💻 **Modern Glassmorphic UI**: High-performance dashboard built with React 19, TypeScript, Tailwind CSS, TanStack Query, Recharts, and XYFlow graph visualizations.

---

## 4. System Architecture

The platform is designed around strict **Clean Architecture (Onion Architecture)** principles, isolating core business domain models from external drivers, frameworks, and storage backends.

```mermaid
flowchart TD
    subgraph UI ["Presentation Layer (React 19 + TypeScript + Vite)"]
        Dashboard["Dashboard & KPIs"]
        Chat["Grounded Chat & Citations"]
        KBPage["Knowledge Base & Health Center"]
        Playground["Search Playground (Side-by-Side)"]
        Workflows["Agent Workflow Visualizer"]
        Obs["Observability & Traces Waterfall"]
    end

    subgraph API ["API & Gateway Layer (FastAPI 0.115+)"]
        ReqMiddleware["RequestId & TraceId Correlation"]
        SecHeaders["Security Headers Middleware"]
        AuthRoute["Auth & Session Management (Argon2id + JWT)"]
        APIRouter["API Router (/api/v1/)"]
    end

    subgraph Service ["Application & Agent Layer"]
        Orchestrator["LangGraph Agentic Orchestrator (10 Nodes)"]
        CollabGraph["Multi-Agent Collaboration Graph (8 Nodes)"]
        IngestionService["Ingestion & Chunker Service"]
        RetrievalService["Retrieval Fusion Service"]
        HealthService["KB Integrity & Repair Service"]
        RecoveryEngine["Self-Healing Policy & Classifier"]
        EvalRunner["Evaluation Benchmark Runner"]
        ObsService["Observability & Cost Tracer"]
    end

    subgraph Domain ["Domain Abstractions & Interfaces"]
        ILLM["LLMProviderInterface"]
        IEmbed["EmbeddingProviderInterface"]
        IRerank["RerankerInterface"]
        IStore["StorageProviderInterface"]
        IConnector["BaseConnector"]
    end

    subgraph Infra ["Infrastructure & Storage Backends"]
        Groq["Groq Cloud (LLaMA 3.3 70B)"]
        OpenAI["OpenAI (GPT-4o / Synthesis)"]
        FastEmbed["FastEmbed ONNX (BAAI/bge-small-en-v1.5)"]
        FlashRank["FlashRank Cross-Encoder (TinyBERT)"]
        PG["PostgreSQL 16 + pgvector (Async SQLAlchemy 2.0)"]
        Redis["Redis 7 (Session Cache & Rate Limiting)"]
        Disk["Local Storage / S3 MinIO"]
    end

    UI -->|JSON REST + HttpOnly Cookies| API
    API --> Service
    Service --> Domain
    Domain --> Infra
    Orchestrator -.->|Self-Healing Retry Loop| RetrievalService
    RecoveryEngine -.->|Diagnose & Rewrite| Orchestrator
```

### Architectural Layer Responsibilities

| Layer | Folder Path | Primary Responsibility |
| :--- | :--- | :--- |
| **Presentation** | `frontend/src/` | Interactive glassmorphic SPA, route guards, citation drawers, waterfall spans, and real-time state management. |
| **API & Routing** | `backend/app/api/` | HTTP request routing, Pydantic schema validation, rate limits, exception mapping, and correlation ID tracing. |
| **Core & Security** | `backend/app/core/` | Pydantic Settings management, Argon2id hashing, JWT token issuance, structured JSON logging, and security headers. |
| **Application Services** | `backend/app/services/` | Business orchestrators, LangGraph state machines, multi-format document parsers, chunking algorithms, and self-healing logic. |
| **Domain Interfaces** | `backend/app/domain/` | Abstract provider contracts (`LLMProviderInterface`, `EmbeddingProviderInterface`, `RerankerInterface`) preventing vendor lock-in. |
| **Infrastructure** | `backend/app/infrastructure/` | Concrete implementations: Groq API client, FastEmbed ONNX runner, FlashRank cross-encoder, SQLAlchemy async models, and Redis caches. |

---

## 5. Technology Stack

### Frontend Application
| Technology | Version | Purpose |
| :--- | :--- | :--- |
| **React** | `19.2.8` | Declarative user interface framework |
| **TypeScript** | `~6.0.2` | Compile-time type safety across all components and API clients |
| **Vite** | `^8.3.0` | Ultra-fast client build tool and HMR development server |
| **Tailwind CSS** | `^4.3.3` | Utility-first responsive CSS styling with dark-mode palette |
| **TanStack React Query** | `^5.104.1` | Asynchronous server-state caching, invalidation, and fetching |
| **XYFlow (@xyflow/react)** | `^12.12.0` | Interactive node-based agent workflow graph visualization |
| **Recharts** | `^3.10.1` | Real-time charts for latency, token usage, and evaluation metrics |
| **Lucide React** | `^1.53.0` | Modern, consistent icon library |
| **React Router** | `^7.18.4` | Client-side declarative routing and protected route guards |
| **Vitest** | `^5.0.3` | Frontend unit and integration test runner |
| **Oxlint** | `^1.81.0` | High-performance linter for TypeScript and JSX |

### Backend Application
| Technology | Version | Purpose |
| :--- | :--- | :--- |
| **Python** | `3.11+ / 3.13` | Backend runtime environment |
| **FastAPI** | `>=0.115.0` | Asynchronous high-performance REST framework |
| **Uvicorn** | `>=0.32.0` | Lightning-fast ASGI production web server |
| **Pydantic & Settings** | `>=2.9.0` | Type validation, schema serialization, and environment parsing |
| **SQLAlchemy (Async)** | `>=2.0.35` | Modern async ORM with `asyncpg` database driver |
| **Alembic** | `>=1.13.3` | Database schema migrations and versioning |
| **LangGraph** | `>=0.2.0` | Cyclic, stateful multi-agent decision graph framework |
| **PyPDF & python-docx** | `>=5.0.0` | Robust PDF and Microsoft Word document text extraction |
| **Argon2-cffi** | `>=23.1.0` | State-of-the-art cryptographic password hashing |
| **PyJWT** | `>=2.8.0` | RFC 7519 JSON Web Token signing and verification |
| **HTTPX** | `>=0.27.2` | Async HTTP client for outbound API requests and LLM endpoints |
| **Pytest & pytest-asyncio**| `>=8.3.0` | Automated async backend test execution framework |
| **Ruff** | `>=0.7.0` | Extremely fast Python linter and code formatter |

### Database, AI & Vector Retrieval
| Component | Implementation | Model / Driver | Configuration |
| :--- | :--- | :--- | :--- |
| **Primary Database** | PostgreSQL 16+ | `asyncpg` | Full ACID persistence for users, documents, traces, and metrics |
| **Vector Indexing** | `pgvector` | HNSW / Cosine distance | 384-dimensional embeddings stored in `document_chunks` |
| **Sparse Retrieval** | `rank-bm25` | BM25Plus algorithm | Lexical keyword ranking with custom tokenization |
| **Dense Embeddings** | FastEmbed | `BAAI/bge-small-en-v1.5` | ONNX CPU runtime (384 dimensions, zero external API latency) |
| **Cross-Reranker** | FlashRank | `ms-marco-TinyBERT-L-2-v2` | Neural cross-encoder reranking running locally on CPU |
| **Production LLM** | Groq Cloud | `llama-3.3-70b-versatile` | Ultra-fast inference provider for synthesis and query rewriting |
| **Fallback LLM** | OpenAI API | `gpt-4o-mini` | Pluggable alternative synthesis and evaluation model |
| **Distributed Cache** | Redis 7 | `redis.asyncio` | Session token tracking, distributed locking, and rate limiting |

---

## 6. Project Directory Structure

```text
Self-Healing RAG Agent/
├── .github/
│   └── workflows/
│       └── ci.yml                 # GitHub Actions CI (Backend lint/pytest + Frontend vitest/build)
├── backend/
│   ├── alembic/
│   │   ├── versions/              # 9 sequential database migration revisions (0001 -> 0009)
│   │   └── env.py                 # Async Alembic runtime environment
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/            # 13 route modules (auth, kb, docs, retrieval, agents, eval, obs)
│   │   │   └── router.py          # Central API v1 router aggregator
│   │   ├── core/                  # Config, logging, error taxonomy, security, and middleware
│   │   ├── domain/                # Abstract interfaces (LLM, Embeddings, Reranker, Storage)
│   │   ├── infrastructure/        # Concrete drivers: pgvector, Groq, FastEmbed, FlashRank, Redis
│   │   ├── repositories/          # Database repositories (User, KB, Document, AuditLog)
│   │   ├── schemas/               # Typed Pydantic request and response schemas
│   │   ├── services/
│   │   │   ├── agent/             # LangGraph state graph, nodes, and collaborative workflows
│   │   │   ├── connectors/        # External sources (GitHub, PostgreSQL, Web, GDrive, Notion)
│   │   │   ├── evaluation/        # Benchmark datasets, math metrics, and runner
│   │   │   ├── knowledge_base/    # Integrity health checks, duplicate review, and zero-downtime repair
│   │   │   ├── observability/     # Distributed tracer, token/cost attribution, error explorer
│   │   │   ├── parsers/           # 9 document parsers (PDF, DOCX, XLSX, HTML, Markdown, CSV, etc.)
│   │   │   ├── recovery/          # Self-healing failure classifier, rewriter, and adaptive policy
│   │   │   └── retrieval/         # Hybrid fusion engine (pgvector + BM25 + RRF + FlashRank)
│   │   └── main.py                # FastAPI factory, lifespan manager, and CORS middleware
│   ├── tests/                     # 272 automated pytest test suites covering all phases
│   ├── requirements.txt           # Production backend dependencies
│   └── requirements-dev.txt       # Development and testing dependencies
├── frontend/
│   ├── src/
│   │   ├── components/            # UI components (cards, tables, modals, citation drawers, flow charts)
│   │   ├── context/               # AuthContext, ThemeContext, ToastContext
│   │   ├── hooks/                 # Custom React hooks (useAuth, useKnowledgeBase, useHealth)
│   │   ├── pages/                 # Full dashboard pages (Dashboard, Chat, KB, Search, Agents, Eval, Obs)
│   │   ├── routes/                # Client-side router with protected route guards
│   │   ├── services/              # API clients mapped to backend endpoints
│   │   ├── types/                 # TypeScript interfaces and domain models
│   │   └── App.tsx                # Main frontend application shell
│   ├── package.json               # Frontend dependencies and scripts
│   └── vite.config.ts             # Vite build configuration with development proxy
├── docker/
│   ├── Dockerfile.backend         # Production container for FastAPI backend
│   ├── Dockerfile.frontend        # Multi-stage production container for React Vite SPA
│   └── postgres/init-extensions.sql # PostgreSQL init script enabling pgvector
├── docs/                          # Architecture guides, database docs, API references, roadmap
├── scripts/                       # Dev startup scripts, E2E verification, benchmark runners
├── .env.example                   # Root environment configuration template with safe placeholders
├── docker-compose.yml             # Full 4-service stack (Postgres pgvector, Redis, Backend, Frontend)
├── CONTRIBUTING.md                # Contribution workflow and code standards
├── LICENSE                        # MIT License
└── README.md                      # Comprehensive project documentation
```

---

## 7. End-to-End AI & RAG Pipeline

```text
 1. DOCUMENT INGESTION & VALIDATION
    Uploaded File (PDF, DOCX, XLSX, HTML, etc.)
      │
      ▼
 2. PARSING & TEXT EXTRACTION
    Format-specific parser extracts clean text, strips scripts, normalizes Unicode
      │
      ▼
 3. RECURSIVE CHUNKING & METADATA
    Sliding window chunking (500 tokens, 50 overlap) with byte offsets & checksums
      │
      ▼
 4. LOCAL VECTOR EMBEDDING
    FastEmbed (BAAI/bge-small-en-v1.5) generates 384-dimensional dense vectors
      │
      ▼
 5. DUAL-INDEX PERSISTENCE
    Chunks stored in PostgreSQL with pgvector embeddings + text tsvector for BM25
      │
      ▼
 6. HYBRID CANDIDATE RETRIEVAL
    Dense Semantic Search (pgvector)  +  Sparse Lexical Search (BM25Plus)
      │                                       │
      └───────────────────┬───────────────────┘
                          ▼
 7. RECIPROCAL RANK FUSION (RRF) & RERANKING
    RRF score: score(d) = Σ 1 / (60 + rank_i(d))
    Top candidates reranked by FlashRank Cross-Encoder (TinyBERT)
      │
      ▼
 8. EVIDENCE ASSESSMENT & VERIFICATION SHIELD
    Chunks checked for coverage & relevance. If insufficient ──► [Trigger Self-Healing]
      │
      ▼
 9. GROUNDED LLM SYNTHESIS
    Groq (LLaMA 3.3 70B) generates answer constrained strictly to retrieved context
      │
      ▼
10. CITATION EXTRACTION & AUDIT
    Audits bracketed tags [1], [2] against chunk bounds; verifies factual alignment
      │
      ▼
11. TELEMETRY & OBSERVABILITY
    Traces latency waterfall, token counts, and estimated cost in execution_traces
```

### 1. Document Parsing & Ingestion
Documents are processed through specialized parsers registered in `ParserFactory`:
- **PDF**: `pypdf` extracting text streams, headings, and page boundaries.
- **DOCX / XLSX**: Table cell extraction, preserving tabular layout and column relationships.
- **HTML / Web**: Strips scripts, navigation chrome, and styles, isolating article text.
- **Markdown / CSV / JSON**: Preserves structure, keys, and hierarchical values.

### 2. Hybrid Retrieval with Reciprocal Rank Fusion (RRF)
To eliminate vocabulary mismatch, queries run concurrently through two distinct retrieval engines:
1. **Semantic Vector Search**: Uses cosine distance over 384-dimensional vectors stored in PostgreSQL via `pgvector`.
2. **Lexical BM25 Search**: Matches exact keyword occurrences, jargon, and alphanumeric identifiers using `rank-bm25`.

The candidate lists are merged using **Reciprocal Rank Fusion**:
$$\text{RRF Score}(d) = \sum_{m \in \{\text{vector}, \text{bm25}\}} \frac{1}{k + \text{rank}_m(d)} \quad (k=60)$$

### 3. Neural Cross-Encoder Reranking
The top fused candidates are evaluated by **FlashRank** (`ms-marco-TinyBERT-L-2-v2`), a lightweight neural cross-encoder. It scores query-document token interactions simultaneously, boosting true relevance far above simple bi-encoder cosine similarity.

---

## 8. Self-Healing & Recovery Mechanism

The Self-Healing Engine operates as a closed-loop controller within the LangGraph workflow, ensuring that retrieval or synthesis anomalies trigger automatic, bounded remediation.

```mermaid
flowchart TD
    Anom[Anomaly Detected during Execution] --> Classify[FailureClassifier Diagnoses Mode]
    
    Classify --> Cat1[Transient Error: Timeout / 429]
    Classify --> Cat2[Low Relevance: Below Threshold]
    Classify --> Cat3[Insufficient Context: Empty Results]
    Classify --> Cat4[Hallucination / Citation Failure]
    Classify --> Cat5[Permanent: 401 / Scope Violation]

    Cat1 --> Act1[Action: RETRY_TRANSIENT with Backoff]
    Cat2 --> Act2[Action: FALLBACK_STRATEGY to Hybrid / BM25]
    Cat3 --> Act3[Action: REWRITE_QUERY & EXPAND_RETRIEVAL]
    Cat4 --> Act4[Action: REGENERATE_WITH_FEEDBACK]
    Cat5 --> Act5[Action: TERMINATE_NON_RECOVERABLE]

    Act1 & Act2 & Act3 & Act4 --> Policy{RecoveryPolicy Budget Check}
    Policy -- Attempts < Max (2) & Time < 45s --> Resume[Resume LangGraph Execution]
    Policy -- Budget Exhausted --> Graceful[Return Honest Insufficient-Evidence Response]
```

### Failure Taxonomy & Allowlisted Actions

The failure classifier maps runtime outcomes into explicit categories:

| Failure Category | Trigger Condition | Automated Recovery Action |
| :--- | :--- | :--- |
| `retrieval_failure` | Downstream connection error, timeout, or Redis lock delay | `RETRY_TRANSIENT` with exponential backoff |
| `low_relevance_evidence` | Cross-encoder reranker scores fall below minimum confidence threshold | `FALLBACK_STRATEGY` (switches from vector to hybrid or relaxes filters) |
| `insufficient_evidence` | Query returns 0 chunks matching the knowledge base | `REWRITE_QUERY` (reformulates query) and `EXPAND_RETRIEVAL` (candidate limit increases from 20 to 35) |
| `citation_failure` | Generated response contains invalid citations (e.g. `[9]` when only 3 chunks exist) | `REPAIR_CITATIONS` (strips invalid references or re-indexes citations) |
| `verification_failure` | Hallucination shield detects ungrounded claims in generated answer | `REGENERATE_WITH_FEEDBACK` (tightens system prompt instructions) |
| `non_recoverable_failure` | Permanent 401/403 permission error or non-existent knowledge base | `TERMINATE_NON_RECOVERABLE` (fails immediately without wasting retries) |

### Strict Bounded Safety Guardrails
To prevent infinite retry loops and uncontrolled token consumption, the recovery engine enforces three non-negotiable boundaries:
1. **Max Attempt Budget**: Enforced strictly at `RECOVERY_MAX_ATTEMPTS=2`.
2. **Global Execution Deadline**: Workflows terminate if execution exceeds `RECOVERY_TIMEOUT_SECONDS=45.0`.
3. **Anti-Cycling Action Tracking**: The system tracks its history of actions and queries, preventing the repetition of failed reformulation strategies.
4. **Graceful Insufficient-Evidence Fallback**: When retry attempts are exhausted, the agent returns a structured statement: *"Based on the retrieved documents, there is insufficient evidence to answer this question."*

---

## 9. Multi-Agent Collaboration Engine

In addition to the standard single-agent pipeline, the platform implements a **Multi-Agent Collaborative Workflow** (`POST /api/v1/agents/collaborate`) for complex analytical questions requiring subtask decomposition:

```mermaid
graph TD
    UserQuery[Complex User Query] --> Coord[1. Query Understanding & Planning Agent]
    Coord --> TenantGuard[2. Scope & Tenant Authorization Guard]
    TenantGuard --> Plan[3. Subtask Decomposition]
    Plan --> RetAgent[4. Retrieval Agent: Subtask-Aware Hybrid Search]
    RetAgent --> EvidAgent[5. Evidence Analysis Agent: Provenance Scoring]
    EvidAgent --> FactCheck[6. Verification Agent: Fact & Citation Shield]
    FactCheck --> SynthAgent[7. Synthesis Agent: Cross-Source Grounding]
    SynthAgent --> Supervisor[8. Supervisor Coordinator: Final Review]
    Supervisor --> Output[Consolidated Verified Response]
```

1. **Query Understanding Agent**: Dissects multi-faceted questions into clear, independent sub-queries.
2. **Planning Agent**: Decomposes dependencies (e.g., determining prerequisite policies before evaluating compliance).
3. **Retrieval Agent**: Executes targeted hybrid searches for each subtask independently.
4. **Evidence Analysis Agent**: Scores provenance, freshness, and relevance across all retrieved evidence sets.
5. **Verification Agent**: Validates claims across sources to prevent contradictions and false extrapolations.
6. **Synthesis Agent**: Assembles the final answer with unified cross-document citations.
7. **Supervisor Coordinator**: Audits the overall response, aggregates token counts, and commits the execution trace.

---

## 10. Evaluation & Observability Intelligence

### Mathematical Evaluation Metrics (`app.services.evaluation.metrics`)

The evaluation engine computes empirical metrics against golden benchmark datasets:

- **Precision@K**: Fraction of top-$K$ retrieved chunks that are genuinely relevant:
  $$\text{Precision@}K = \frac{|\text{Retrieved}_K \cap \text{Relevant}|}{K}$$
- **Recall@K**: Fraction of all relevant ground-truth chunks successfully retrieved:
  $$\text{Recall@}K = \frac{|\text{Retrieved}_K \cap \text{Relevant}|}{|\text{Relevant}|}$$
- **Mean Reciprocal Rank (MRR)**: Evaluates how high the first relevant chunk appears:
  $$\text{MRR} = \frac{1}{\text{rank}_1}$$
- **nDCG@K (Normalized Discounted Cumulative Gain)**: Measures ranking quality penalizing relevant documents appearing lower in the candidate list.
- **Groundedness Score**: Ratio of verifiable sentences in the generated answer supported by retrieved text snippets. Truthful insufficient-evidence answers receive a faithful score of 1.0.
- **Citation Validity**: Validates that all bracketed citation numbers `[i]` fall within range ($1 \le i \le N$).

### Production Observability & Distributed Traces

Every request through `/api/v1/` generates a structured, distributed execution trace stored in PostgreSQL (`execution_traces` and `trace_spans`):

- **Span Waterfalls**: Granular timing breakdowns across every stage (`query_analysis`, `retrieval`, `rerank`, `generation`, `verification`, `recovery`).
- **Cost & Token Attribution**: Real-time token consumption tracked for prompt and completion tokens, with live cost estimation based on the active provider pricing catalog (e.g., Groq LLaMA 3.3 @ $0.59 / $0.79 per 1M tokens).
- **Error Explorer**: Automatically groups pipeline exceptions by error taxonomy and surfaces actionable debugging suggestions in the dashboard.
- **Automated Reliability Alerts**: Real-time evaluation of error rate spikes, latency percentiles ($p50$, $p95$, $p99$), and low groundedness ratios.

---

## 11. REST API Catalog

The backend exposes **53 fully implemented endpoints** under `/api/v1/`. Interactive documentation is available at:
- **Swagger UI**: `http://localhost:8000/api/v1/docs`
- **ReDoc**: `http://localhost:8000/api/v1/redoc`
- **OpenAPI Schema**: `http://localhost:8000/api/v1/openapi.json`

### Authentication & Session Management
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register` | Register new user account with Argon2id password hashing | Public |
| `POST` | `/api/v1/auth/login` | Authenticate user; returns JWT access token and sets refresh cookie | Public |
| `POST` | `/api/v1/auth/demo-login` | Development-only quick login (`demo@selfhealingrag.local`) | Development Only |
| `POST` | `/api/v1/auth/refresh` | Rotate refresh token family and issue new access token | Refresh Cookie |
| `POST` | `/api/v1/auth/logout` | Revoke active user session | Authenticated |
| `POST` | `/api/v1/auth/logout-all` | Invalidate all active sessions across all devices | Authenticated |
| `GET` | `/api/v1/auth/me` | Retrieve authenticated profile and assigned role | Authenticated |
| `GET` | `/api/v1/auth/sessions` | List all active sessions and device information | Authenticated |
| `DELETE`| `/api/v1/auth/sessions/{id}`| Revoke a specific active session | Authenticated |
| `POST` | `/api/v1/auth/change-password` | Update account password and revoke other sessions | Authenticated |
| `POST` | `/api/v1/auth/forgot-password` | Request password reset token | Public |
| `GET` | `/api/v1/auth/config` | Public auth configuration and demo login availability | Public |

### Knowledge Bases & Health Management
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/knowledge-bases` | List all knowledge bases owned by the user | Authenticated |
| `POST` | `/api/v1/knowledge-bases` | Create a new knowledge base | Authenticated |
| `GET` | `/api/v1/knowledge-bases/{id}` | Retrieve knowledge base details, document counts, and status | Authenticated |
| `PATCH` | `/api/v1/knowledge-bases/{id}` | Update knowledge base name or description | Authenticated |
| `DELETE`| `/api/v1/knowledge-bases/{id}`| Delete knowledge base and cascade-delete all chunks | Authenticated |
| `GET` | `/api/v1/knowledge-bases/{id}/health` | Evaluate comprehensive indexing integrity and health findings | Authenticated |
| `GET` | `/api/v1/knowledge-bases/{id}/duplicates`| Detect exact checksum duplicates and semantic near-duplicates | Authenticated |
| `GET` | `/api/v1/knowledge-bases/{id}/conflicts` | Detect factual or policy contradictions across documents | Authenticated |
| `GET` | `/api/v1/knowledge-bases/{id}/coverage` | Analyze empirical knowledge coverage and evidence sufficiency | Authenticated |
| `GET` | `/api/v1/knowledge-bases/{id}/documents`| List all documents within a knowledge base | Authenticated |
| `POST` | `/api/v1/knowledge-bases/{id}/documents`| Upload document (`multipart/form-data`) and trigger ingestion | Authenticated |
| `POST` | `/api/v1/knowledge-bases/{id}/documents/{doc_id}/repair` | Trigger targeted repair (`RECONCILE_STALE`, `REINDEX_ORPHANS`) | Authenticated |
| `POST` | `/api/v1/knowledge-bases/{id}/documents/{doc_id}/reindex` | Zero-downtime document reindexing via staging chunk table | Authenticated |
| `GET` | `/api/v1/knowledge-bases/{id}/documents/{doc_id}/versions` | List historical versions and chunk counts for a document | Authenticated |
| `GET` | `/api/v1/knowledge-bases/{id}/repair-jobs` | List background repair jobs for this knowledge base | Authenticated |
| `POST` | `/api/v1/knowledge-bases/{id}/search` | Execute retrieval scoped to a specific knowledge base | Authenticated |

### Document Lifecycle
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/documents/{id}` | Get document status, metadata, and chunk count | Authenticated |
| `DELETE`| `/api/v1/documents/{id}` | Delete document, removing physical files and vector chunks | Authenticated |
| `GET` | `/api/v1/documents/{id}/chunks` | Retrieve chunk snippets and citation metadata for a document | Authenticated |
| `GET` | `/api/v1/documents/{id}/download` | Download original uploaded document file | Authenticated |
| `POST` | `/api/v1/documents/{id}/reprocess` | Re-run ingestion and embedding pipeline on an existing document | Authenticated |

### Retrieval & Search Playground
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/retrieval/search` | Execute hybrid, vector, or BM25 search with FlashRank reranking | Authenticated |
| `POST` | `/api/v1/retrieval/compare`| Compare Vector, BM25, and Hybrid results side-by-side | Authenticated |
| `POST` | `/api/v1/search` | Root search alias for `/api/v1/retrieval/search` | Authenticated |

### Grounded Chat & Agent Workflows
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/chat` | Generate grounded conversational response with sentence citations | Authenticated |
| `GET` | `/api/v1/agents/graph` | Retrieve active LangGraph workflow topology and node configuration | Authenticated |
| `POST` | `/api/v1/agents/run` | Execute 10-node agentic RAG workflow with self-healing recovery | Authenticated |
| `POST` | `/api/v1/agents/collaborate` | Execute Phase 16 Multi-Agent Collaborative workflow | Authenticated |

### Data Sources & External Connectors
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/data-sources` | List configured external data connectors | Authenticated |
| `POST` | `/api/v1/data-sources` | Configure new connector (GitHub, Postgres, Web, Notion, GDrive)| Authenticated |
| `GET` | `/api/v1/data-sources/{id}` | Retrieve data source details with masked credentials | Authenticated |
| `PUT` | `/api/v1/data-sources/{id}` | Update data source configuration | Authenticated |
| `DELETE`| `/api/v1/data-sources/{id}` | Delete data source configuration | Authenticated |
| `POST` | `/api/v1/data-sources/{id}/test` | Test external connector reachability and credentials | Authenticated |
| `GET` | `/api/v1/data-sources/{id}/items` | Discover and browse remote documents, repos, or tables | Authenticated |
| `POST` | `/api/v1/data-sources/{id}/sync` | Sync selected remote items into a target knowledge base | Authenticated |

### Evaluation & Observability
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/evaluation/datasets` | List available registered benchmark datasets | Authenticated |
| `GET` | `/api/v1/evaluation/runs` | List historical evaluation benchmark runs | Authenticated |
| `POST` | `/api/v1/evaluation/runs` | Trigger automated evaluation benchmark execution | Authenticated |
| `GET` | `/api/v1/evaluation/runs/{id}` | View detailed case breakdown and metric scores for a run | Authenticated |
| `GET` | `/api/v1/evaluation/metrics/summary` | Retrieve aggregated accuracy and groundedness KPIs | Authenticated |
| `GET` | `/api/v1/observability/overview` | High-level reliability KPIs: requests, latency, tokens, cost | Authenticated |
| `GET` | `/api/v1/observability/metrics` | Real-time percentiles ($p50$, $p95$, $p99$) and stage breakdowns | Authenticated |
| `GET` | `/api/v1/observability/traces` | Query paginated distributed request traces | Authenticated |
| `GET` | `/api/v1/observability/traces/{id}`| Retrieve detailed trace span waterfall with payload data | Authenticated |
| `GET` | `/api/v1/observability/errors` | Error Explorer: grouped error taxonomy and root cause suggestions | Authenticated |
| `GET` | `/api/v1/observability/alerts` | List active reliability alerts and threshold violation history | Authenticated |
| `GET` | `/api/v1/observability/pricing` | View active model token pricing catalog | Authenticated |

### Health & System
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Basic application health and version check | Public |
| `GET` | `/api/v1/health/live` | Kubernetes liveness probe | Public |
| `GET` | `/api/v1/health/ready` | Readiness probe checking PostgreSQL and Redis connectivity | Public |
| `GET` | `/api/v1/system/info` | Application metadata and runtime environment | Public |

---

## 12. Database Schema & Persistence

The relational schema is managed through 9 sequential **Alembic** migrations using PostgreSQL 16:

```
┌──────────────┐       ┌──────────────────────┐       ┌─────────────────┐
│    users     │───┬───│   knowledge_bases    │───────│    documents    │
└──────────────┘   │   └──────────────────────┘       └─────────────────┘
                   │                                           │
                   │                                           ▼
                   │   ┌──────────────────────┐       ┌─────────────────┐
                   ├───│     data_sources     │       │ document_chunks │
                   │   └──────────────────────┘       │ (pgvector 384d) │
                   │                                  └─────────────────┘
                   │   ┌──────────────────────┐
                   ├───│   execution_traces   │
                   │   └──────────────────────┘
                   │               │
                   │               ▼
                   │   ┌──────────────────────┐
                   │   │     trace_spans      │
                   │   └──────────────────────┘
                   │
                   │   ┌──────────────────────┐
                   └───│   evaluation_runs    │
                       └──────────────────────┘
```

1. **`users` & `user_sessions`**: User identity, Argon2id password hash, RBAC roles (`USER`, `ADMIN`), and cryptographically secure refresh token family hashes for session rotation.
2. **`knowledge_bases`**: Scoped multi-tenant knowledge collections with status flags (`ACTIVE`, `MAINTENANCE`, `ARCHIVED`).
3. **`documents` & `document_versions`**: Document tracking, storage paths, mime types, file sizes, processing status (`PENDING`, `PROCESSING`, `ACTIVE`, `FAILED`), and sha256 checksums.
4. **`document_chunks`**: Text content, token offsets, chunk index, metadata JSON, and `embedding` (`ResilientVector(dim=384)` with HNSW cosine index).
5. **`execution_traces` & `trace_spans`**: Distributed request tracing records storing prompt tokens, completion tokens, latency, cost in USD, and span waterfalls.
6. **`evaluation_runs` & `evaluation_case_results`**: Historical benchmark records storing Precision@K, Recall@K, MRR, nDCG, and groundedness metrics.
7. **`data_sources`**: External connector credentials and synchronization configurations with sensitive fields masked.
8. **`kb_repair_jobs`**: Audit trail of zero-downtime document repair and reindexing operations.

---

## 13. Security, Governance & Isolation

- 🔒 **Zero Hardcoded Credentials**: No API keys, passwords, or tokens are committed to source control or exposed to the client. All backend keys remain strictly server-side.
- 🏢 **Strict Tenant Data Isolation**: Every database query for knowledge bases, documents, chunks, data sources, and traces is filtered by `user_id`, preventing cross-tenant leakage.
- 🔑 **Cryptographic Authentication**:
  - Passwords hashed using **Argon2id** (memory cost 65,536 KiB, time cost 3 iterations).
  - Short-lived JWT access tokens (15-minute expiration).
  - Rotated refresh token families stored in secure `HttpOnly`, `SameSite=Lax` cookies with automated token-reuse detection (reusing an old token revokes the entire family).
- 🙈 **Automated Secret Redaction Pipeline**:
  - `KEY_REDACT_REGEX` and `redact_sensitive_data` automatically strip Groq keys (`gsk_*`), OpenAI keys (`sk-*`), Bearer tokens, passwords, and cookies from all logs and trace spans.
  - Connector configurations mask credentials (e.g. `ghp_...` → `ghp_1234...wxyz`).
- 🛡️ **Safe Error Handling**: Internal stack traces and database connection URLs are caught by global exception handlers and masked into standardized error codes (`AppError`).
- 🛑 **Production Demo Login Boundary**: Development demo login (`DEMO_LOGIN_ENABLED`) is strictly blocked (returns HTTP 403) whenever `APP_ENV=production`.

---

## 14. Local Development Setup

### Prerequisites

- **Python**: Version `3.11` or higher (verified on Python 3.13)
- **Node.js**: Version `20.x` or higher (verified on Node v24.20 / npm 11.19)
- **PostgreSQL**: Version `16+` with `pgvector` extension enabled
- **Redis** (Optional): Version `7+` (set `REDIS_ENABLED=false` for in-memory session handling)

### Step 1: Clone the Repository

```bash
git clone https://github.com/Jeeva1117/Self-Healing-RAG-Agent.git
cd Self-Healing-RAG-Agent
```

### Step 2: Configure Environment Files

Copy the provided safe configuration templates:

```powershell
# Windows PowerShell:
Copy-Item .env.example .env
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.example frontend\.env
```

```bash
# Linux / macOS:
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Edit `.env` and `backend/.env` to configure your PostgreSQL credentials and LLM provider key:
```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/self_healing_rag
GROQ_API_KEY=your_groq_api_key_here
LLM_PROVIDER=groq
```

### Step 3: Setup Backend Environment

```powershell
# Windows PowerShell:
python -m venv backend\.venv
.\backend\.venv\Scripts\pip install -r backend\requirements-dev.txt
```

```bash
# Linux / macOS:
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements-dev.txt
```

### Step 4: Apply Database Migrations

Ensure your PostgreSQL instance is running with `pgvector`, then run:

```powershell
# Windows PowerShell (from workspace root):
.\backend\.venv\Scripts\alembic.exe -c alembic.ini upgrade head
```

```bash
# Linux / macOS (from workspace root):
backend/.venv/bin/alembic -c alembic.ini upgrade head
```

### Step 5: Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

### Step 6: Start Development Servers

Open two terminals:

**Terminal 1 — Backend API:**
```powershell
# Windows PowerShell:
.\backend\.venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
```
```bash
# Linux / macOS:
source backend/.venv/bin/activate
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — Frontend Application:**
```bash
# From workspace root:
npm run dev
# Or from frontend folder:
cd frontend && npm run dev
```

### Step 7: Access the Application

- **Web Dashboard**: [http://localhost:5173](http://localhost:5173)
- **API Swagger Documentation**: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
- **API ReDoc Documentation**: [http://localhost:8000/api/v1/redoc](http://localhost:8000/api/v1/redoc)

> **Quick Access Demo**: For local testing without manual registration, set `DEMO_LOGIN_ENABLED=true` in `.env` and click **Demo Login** on the login screen (`demo@selfhealingrag.local`).

---

## 15. Environment Configuration

All settings are managed via Pydantic Settings in `backend/app/core/config.py`.

| Variable Name | Default Value | Required? | Description |
| :--- | :--- | :--- | :--- |
| `APP_ENV` | `development` | Optional | Runtime mode: `development`, `staging`, `production`, `test` |
| `HOST` | `0.0.0.0` | Optional | Backend listening host interface |
| `PORT` | `8000` | Optional | Backend listening port |
| `LOG_LEVEL` | `INFO` | Optional | Structured logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `DATABASE_URL` | `postgresql+asyncpg://...` | **Required** | Async PostgreSQL connection string with pgvector |
| `REDIS_URL` | `redis://localhost:6379/0` | Optional | Redis connection URL for session storage and locks |
| `REDIS_ENABLED` | `true` | Optional | Enable Redis cache (`false` falls back to in-memory handling) |
| `JWT_SECRET` | *(Placeholder)* | **Required in Prod** | 32+ character cryptographic secret for signing JWTs |
| `DEMO_LOGIN_ENABLED`| `false` | Optional | Enable single-click local development login |
| `CORS_ORIGINS` | `http://localhost:5173,...`| Optional | Comma-separated list of allowed client origin URLs |
| `LLM_PROVIDER` | `groq` | Optional | Active synthesis provider: `groq`, `openai`, `mock` |
| `GROQ_API_KEY` | *(Empty)* | **Required if Groq**| Groq Cloud API key (obtain from console.groq.com) |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Optional | Groq model identifier |
| `EMBEDDING_PROVIDER`| `fastembed` | Optional | Embeddings provider: `fastembed` (local CPU) or `mock` |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Optional | FastEmbed model identifier (384 dimensions) |
| `RERANKER_PROVIDER` | `flashrank` | Optional | Reranker engine: `flashrank` (local CPU) or `mock` |
| `STORAGE_PROVIDER` | `local` | Optional | Physical document storage: `local`, `s3`, `minio` |
| `STORAGE_LOCAL_PATH`| `data/storage` | Optional | Local disk directory for document uploads |
| `RECOVERY_MAX_ATTEMPTS`| `2` | Optional | Maximum retry budget for self-healing loops |
| `RECOVERY_TIMEOUT_SECONDS`| `45.0` | Optional | Maximum timeout for end-to-end agent graph |
| `VITE_API_URL` | `/api/v1` | Optional | Frontend API base proxy path |

---

## 16. Docker & Container Deployment

A complete containerized environment is defined in `docker-compose.yml`:

```bash
# Build and start all 4 services in the background
docker compose up --build -d

# Check service health
docker compose ps

# View backend logs
docker compose logs -f backend

# Stop services
docker compose down
```

### Services in `docker-compose.yml`:
1. **`postgres`**: `pgvector/pgvector:pg16` with volume persistence (`postgres_data`) and automatic extension initialization (`vector`).
2. **`redis`**: `redis:7-alpine` with health check and volume persistence (`redis_data`).
3. **`backend`**: Multi-stage Python 3.11 container running FastAPI under Uvicorn with storage volume mount (`storage_data`).
4. **`frontend`**: React 19 production build served via Nginx on port `5173`.

---

## 17. Testing & Quality Assurance

All test suites and verification checks have been thoroughly executed and verified:

```powershell
# 1. Run Backend Automated Pytest Suite (272 tests)
backend\.venv\Scripts\pytest.exe -o pythonpath=backend backend\tests

# 2. Run Backend Code Quality & Linter
backend\.venv\Scripts\ruff.exe check backend\app backend\tests

# 3. Run Frontend Vitest Unit Tests (46 tests)
npm run test

# 4. Run Frontend Oxlint Linter (0 errors)
npm run lint

# 5. Run Frontend Production TypeScript Build
npm run build
```

### Test Suite Execution Summary
- **Backend Tests**: **272 passed**, 1 skipped (live Groq network test), 0 failed across 21 test files (72.10s execution).
- **Frontend Tests**: **46 passed**, 0 failed across 5 test suites (935ms execution).
- **Frontend Linter**: **0 errors** across 91 files inspected in 295ms.
- **Frontend Build**: TypeScript type-check passed; production bundle emitted in 2.43s.
- **Secret Scanning Audit**: Zero detected secrets or active provider credentials in codebase.

---

## 18. Roadmap & Known Limitations

### Current Operational Boundaries
- **Scanned Image OCR**: Scanned PDF files containing raster images without embedded text layers require optical text extraction; currently flagged with `OCR_REQUIRED`.
- **Distributed Lock Clustering**: Single-instance document repairs utilize in-memory concurrency locks; multi-instance horizontal clusters should enable Redis distributed locking (`REDIS_ENABLED=true`).
- **External Data Connectors**: Third-party integrations (GitHub, Notion, Google Drive) require user-supplied API tokens configured in the Data Sources page.

### Future Roadmap
- [ ] Multi-Modal RAG: Support for image embeddings via CLIP/SigLIP for charts, diagrams, and technical schematics.
- [ ] Asynchronous Celery / ARQ Workers: Offload large multi-gigabyte document batches to dedicated background worker queues.
- [ ] Native OpenTelemetry Traces Export: Direct OTLP exporter integration for Jaeger, Grafana Tempo, and Datadog.
- [ ] Graph-RAG Entity Extraction: Knowledge graph integration with Neo4j for multi-hop relational entity querying.

---

## 19. Contributing & License

### Contributing
Contributions, bug reports, and suggestions are welcome! Please review [CONTRIBUTING.md](CONTRIBUTING.md) for development workflows, branch naming conventions, and pull request checklists.

### License
This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for complete details.

---

<div align="center">

**Self-Healing RAG Agent** — Engineered for verifiable, zero-hallucination enterprise AI synthesis.

Developed by [Jeeva1117](https://github.com/Jeeva1117)

</div>