# Environment Setup & Database Prerequisites

Detailed technical setup instructions for the **Self-Healing RAG Agent** platform.

---

## 1. System Prerequisites

| Dependency | Minimum Version | Recommended | Notes |
| :--- | :--- | :--- | :--- |
| **Python** | 3.11+ | 3.11 / 3.12 | Core backend runtime |
| **Node.js** | 20+ | 20 LTS / 22 LTS | Frontend React toolchain |
| **PostgreSQL** | 16+ | 16 with `pgvector` | Relational & dense vector store |
| **Redis** | 7+ | 7-alpine | Optional caching (graceful fallback) |

---

## 2. PostgreSQL & pgvector Setup

The platform uses PostgreSQL with the `pgvector` extension to store 384-dimensional dense chunk embeddings.

### Local Installation (Native)
1. Install PostgreSQL 16.
2. Install `pgvector`:
   ```sql
   -- Connect to your database as superuser:
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
3. Create the database:
   ```sql
   CREATE DATABASE self_healing_rag;
   ```

### Docker Alternative
You can launch PostgreSQL with pgvector using Docker Compose:
```bash
docker compose up -d postgres
```

---

## 3. Database Migrations

Alembic manages database schemas and tables (`users`, `user_sessions`, `knowledge_bases`, `documents`, `document_chunks`, `data_sources`, `execution_traces`, `evaluation_runs`, etc.).

```powershell
# From workspace root:
backend\.venv\Scripts\alembic.exe -c alembic.ini upgrade head

# Or from backend directory:
cd backend
alembic upgrade head
```

---

## 4. LLM & Embedding Model Configuration

- **Embeddings:** By default, the backend uses `fastembed` (`BAAI/bge-small-en-v1.5`, 384 dimensions) running locally on CPU via ONNX Runtime. No external embedding API key is required.
- **Reranking:** By default, hybrid fusion reranking uses `flashrank` (`ms-marco-TinyBERT-L-2-v2`) running locally on CPU.
- **LLM Synthesis:** Configured via `LLM_PROVIDER=groq`. Obtain a free API key at [console.groq.com](https://console.groq.com) and set:
  ```env
  LLM_PROVIDER=groq
  GROQ_API_KEY=your_groq_api_key_here
  GROQ_MODEL=llama-3.3-70b-versatile
  ```

---

## 5. Troubleshooting Common Startup Issues

### 1. `npm error code ENOENT: Could not read package.json`
- **Cause:** Running `npm run dev` in the repository root without a root `package.json`.
- **Solution:** The root `package.json` now proxies scripts automatically. You can run `npm run dev` from the workspace root or `cd frontend && npm run dev`.

### 2. `ConnectionRefusedError: [Errno 111] Connect call failed ('127.0.0.1', 5432)`
- **Cause:** PostgreSQL is not running or credentials in `.env` are incorrect.
- **Solution:** Verify your PostgreSQL service is active: `net start postgresql-x64-16` or check `docker compose ps`.

### 3. Redis Connection Warning
- **Cause:** Redis is not running on `localhost:6379`.
- **Solution:** Redis is optional. Set `REDIS_ENABLED=false` in `.env` for in-memory session handling.
