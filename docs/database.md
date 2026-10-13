# Database Infrastructure & Schema Design — Self-Healing RAG Agent

## 1. Engine & Driver Selection

- **Database Engine**: PostgreSQL 16+ (or PostgreSQL 18 local instance).
- **Python Driver**: `asyncpg` via `postgresql+asyncpg://...`.
- **Vector Extension**: `pgvector` enabling native HNSW and IVFFlat index structures.
- **Migration Engine**: `Alembic` with full async migration runner.

## 2. Entity Lifecycle & Roadmap

Phase 1 establishes the base persistence layer, declarative mixins, and audit logging table:

```
┌────────────────────────────────────────────────────────┐
│                        Base                            │
│  - id: UUID (Primary Key)                              │
│  - created_at: DateTime(timezone=True)                 │
│  - updated_at: DateTime(timezone=True)                 │
└───────────────────────────┬────────────────────────────┘
                            │
         ┌──────────────────┴──────────────────┐
         │                                     │
┌────────▼──────────────┐             ┌────────▼──────────────┐
│       AuditLog        │             │    Future Entities    │
│ (Active in Phase 1)   │             │  - User               │
│ - action              │             │  - Workspace          │
│ - actor_id            │             │  - Document           │
│ - resource_type       │             │  - DocumentChunk      │
│ - resource_id         │             │  - Conversation       │
│ - status              │             │  - Message            │
│ - details (JSON)      │             │  - Query              │
│ - ip_address          │             │  - RetrievalResult    │
│ - request_id          │             │  - AgentRun           │
└───────────────────────┘             │  - EvaluationRun      │
                                      └───────────────────────┘
```

## 3. Migration Workflows

All database schema evolutions must be performed strictly through Alembic revisions. Never modify tables manually in production.

### Generating a New Migration
```bash
cd backend
alembic revision --autogenerate -m "describe_changes"
```

### Applying Migrations
```bash
cd backend
alembic upgrade head
```

### Rolling Back a Migration
```bash
cd backend
alembic downgrade -1
```

## 4. Connection Pool Configuration

The async engine (`app/infrastructure/database/session.py`) implements connection pooling:
- `pool_size`: 20 connections
- `max_overflow`: 10 burst connections
- `pool_timeout`: 30.0 seconds
- `pool_pre_ping`: True (verifies TCP socket liveness before returning connections to handlers)
