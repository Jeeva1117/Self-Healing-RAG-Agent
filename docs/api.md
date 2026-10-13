# API Specifications & Versioning — Self-Healing RAG Agent

## 1. API Versioning Principle

All application endpoints are strictly partitioned under `/api/v1/`. Root-level or unversioned operational endpoints are forbidden, preserving backward compatibility for enterprise client applications.

## 2. Global Headers & Correlation Tracing

| Header | Type | Description |
| :--- | :--- | :--- |
| `X-Request-ID` | String (UUID) | Distributed request correlation token. If supplied by caller, it is echoed back; otherwise generated on entry. |
| `X-Process-Time` | String (e.g., `4.2ms`) | Server-side execution duration measured across ASGI middleware layers. |

## 3. Standard Response Envelope

All API endpoints return structured JSON. Successful responses provide semantic payloads; failures return standardized error structures:

```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "request_id": "c4b3f120-d66a-4952-b342-e1a5a1e2f7b1",
    "timestamp": "2026-10-08T06:30:00Z"
  }
}
```

### Centralized Error Format
```json
{
  "success": false,
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Resource requested could not be resolved",
    "details": { ... }
  }
}
```

## 4. Phase 1 Operational Endpoints

### `GET /api/v1/health`
Returns instantaneous service availability.
- **Status Code**: `200 OK`
- **Response**:
```json
{
  "status": "ok",
  "service": "self-healing-rag-agent",
  "version": "0.1.0",
  "timestamp": "2026-10-08T06:30:00.000000Z"
}
```

### `GET /api/v1/health/live`
Container / Kubernetes liveness probe verifying process responsiveness.
- **Status Code**: `200 OK`
- **Response**:
```json
{
  "status": "alive",
  "service": "self-healing-rag-agent",
  "uptime_seconds": 142.8
}
```

### `GET /api/v1/health/ready`
Readiness probe verifying live connectivity to PostgreSQL and Redis.
- **Status Code**: `200 OK`
- **Response**:
```json
{
  "status": "ready",
  "service": "self-healing-rag-agent",
  "ready": true,
  "dependencies": {
    "database": {
      "status": "healthy",
      "connected": true,
      "latency_ms": 1.45,
      "details": { "pgvector_extension": true }
    },
    "redis": {
      "status": "healthy",
      "connected": true,
      "latency_ms": 0.82
    }
  }
}
```

### `GET /api/v1/system/info`
Returns environment diagnostics, runtime versions, and active phase subsystem flags.
- **Status Code**: `200 OK`

## 5. Phase Modules & Endpoints
- `/api/v1/auth` (Phase 3: Multi-tenant JWT auth & RBAC)
- `/api/v1/knowledge-bases` & `/api/v1/documents` (Phase 4: Document ingestion & chunk partitioning)
- `/api/v1/retrieval` & `/api/v1/knowledge-bases/{id}/search` (Phase 5: Hybrid BM25 + dense vector similarity with RRF and reranking)
- `/api/v1/chat` (Phase 6: Streaming generation & citation verification)
- `/api/v1/agents` (Phase 7: LangGraph execution workflows)
- `/api/v1/evaluation` (Phase 10: RAGAS & DeepEval benchmarks)
- `/api/v1/observability` (Phase 11: OpenTelemetry trace spans)

## 6. Phase 5 Retrieval & Hybrid Search API

### `POST /api/v1/retrieval/search` (or `POST /api/v1/search`)
Executes hybrid, semantic vector, or BM25 lexical retrieval with optional cross-encoder reranking.

**Headers:**
- `Authorization: Bearer <access_token>`

**Request Body:**
```json
{
  "knowledge_base_id": "17f01e80-75a6-408b-9967-4d0058a9d14c",
  "query": "machine learning experience",
  "mode": "hybrid",
  "enable_reranking": true,
  "top_k": 5,
  "candidate_limit": 20,
  "similarity_threshold": 0.0,
  "rrf_k": 60
}
```

**Response Body:**
```json
{
  "success": true,
  "data": {
    "query": "machine learning experience",
    "knowledge_base_id": "17f01e80-75a6-408b-9967-4d0058a9d14c",
    "mode": "hybrid",
    "retrieval_mode": "hybrid",
    "enable_reranking": true,
    "reranking_enabled": true,
    "reranking_applied": true,
    "candidate_count": 2,
    "returned_count": 2,
    "total_results": 2,
    "results": [
      {
        "chunk_id": "0677ed1d-92ba-44ce-9db6-4685aba90c95",
        "document_id": "4704e852-0924-4417-94b0-00e60a0ebf5a",
        "document_version_id": "ae3bb923-bbb0-4570-a456-de6712c3e81d",
        "document_name": "Jeevanantham_resume.pdf",
        "content": "JEEVANANTHAM A\nJunior AI Engineer...",
        "page_number": null,
        "section_title": null,
        "chunk_index": 0,
        "token_count": 482,
        "character_count": 1975,
        "metadata": { ... },
        "vector_rank": 2,
        "vector_score": 0.758908,
        "semantic_rank": 2,
        "semantic_score": 0.758908,
        "lexical_rank": 1,
        "lexical_score": 5.6367,
        "keyword_rank": 1,
        "bm25_score": 5.6367,
        "rrf_rank": 1,
        "rrf_score": 0.032522,
        "reranker_rank": 1,
        "reranker_score": 0.000173,
        "rerank_score": 0.000173,
        "final_rank": 1,
        "stage_provenance": "hybrid"
      }
    ],
    "latency": {
      "vector_ms": 23.43,
      "lexical_ms": 3.36,
      "fusion_ms": 0.14,
      "rerank_ms": 132.49,
      "total_ms": 733.79
    },
    "latency_ms": 733.79,
    "warnings": []
  },
  "meta": {
    "request_id": "...",
    "timestamp": "..."
  }
}
```

### `POST /api/v1/knowledge-bases/{id}/search`
Executes search scoped directly to the target Knowledge Base URL parameter.
Same request payload (with `knowledge_base_id` inferred from path) and identical response structure.

### `POST /api/v1/retrieval/compare`
Executes Vector, BM25 Lexical, and Hybrid retrieval simultaneously and returns side-by-side results for Playground comparative analysis.

