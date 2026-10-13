# Phase 1: Comprehensive Codebase Audit & Implementation Map

## 1. Executive Summary

This audit assesses the Self-Healing RAG Agent platform's data source connectivity and ingestion capabilities. The application is built with a React/TypeScript frontend, FastAPI backend, PostgreSQL database with vector embeddings (`pgvector` / resilient storage), hybrid retrieval (dense embeddings via FastEmbed + lexical BM25 + Reciprocal Rank Fusion + FlashRank neural reranking), and an agentic generation loop powered by Groq.

While foundational interfaces and connectors were sketched in the codebase, key mismatches between frontend configuration forms and backend connectors, double-indexed database definitions, missing format parsers, and incomplete error handling prevented end-to-end functionality.

---

## 2. Inventory of Components

### 2.1 Frontend UI Components
- **Data Sources Page** (`frontend/src/pages/DataSourcesPage.tsx`):
  - Category filters: `All`, `Local`, `Web`, `Cloud`, `Databases`.
  - Connector Cards: Renders status badge, active configuration details, corpus sync count, and action buttons (`Configure`, `Config`, `Test`, `Sync`, `Delete`).
  - Configuration Modal: Dynamic forms for Web, GitHub, Google Drive, Notion, and PostgreSQL.
  - Discovery & Sync Modal: Lists discoverable items with select/clear controls, knowledge base selection, and real-time sync progress/error display.
- **Knowledge Base Page** (`frontend/src/pages/KnowledgeBasePage.tsx`):
  - Document upload dropzone, allowed extensions list, size limits, chunk drawer viewer, reprocessing triggers.
- **Services & Types** (`frontend/src/services/dataSourcesService.ts`, `frontend/src/types/dataSources.ts`).

### 2.2 Backend Architecture
- **API Endpoints** (`backend/app/api/routes/data_sources.py`):
  - `GET /data-sources/catalog`: Discovers supported connectors and user-specific status.
  - `GET /data-sources`: Lists user's configured connectors.
  - `POST /data-sources`: Configures a new connector.
  - `GET /data-sources/{id}`: Retrieves single connector with masked secrets.
  - `PUT /data-sources/{id}`: Updates connector configuration.
  - `DELETE /data-sources/{id}`: Disconnects and removes a connector.
  - `POST /data-sources/{id}/test`: Tests connectivity, credentials, and network safety.
  - `GET /data-sources/{id}/items`: Browses discoverable items (files, tables, pages).
  - `POST /data-sources/{id}/sync`: Extracts, normalizes, chunks, embeds, and indexes items into the Knowledge Base.
- **Database Models** (`backend/app/infrastructure/database/models.py`):
  - `DataSource`: User-scoped external connection configuration with encrypted/masked secrets.
  - `KnowledgeBase`: Tenant-isolated document collection.
  - `Document`: Uploaded or synchronized source document with versioning, checksum, and storage key.
  - `DocumentChunk`: Text chunks with 384-dimensional dense vectors and citation metadata.
- **Ingestion Pipeline** (`backend/app/services/ingestion_service.py`):
  - Unified pipeline: Validate -> Parse -> Normalize -> Chunk -> Embed -> Store -> Verify -> Ready.

---

## 3. Connector-by-Connector Audit Status

| Connector | Status | Key Issues Identified | Resolution Strategy |
| :--- | :--- | :--- | :--- |
| **Local Files & Manual Upload** | PARTIAL | HTML parser omitted title; XLSX error message mismatch; empty/corrupt file edge cases; MIME mapping gaps. | Fix HTML, XLSX, CSV, JSON, Markdown, DOCX parsers; enhance MIME detection; add unit tests. |
| **Website Scraper** | PARTIAL | Frontend sends `root_url`, connector only checked `url`/`base_url`; missing robots.txt respect; missing rate limiting; redirect SSRF vulnerability. | Normalize URL parameter resolution; add robots.txt parser; enforce SSRF on redirects; add sitemap discovery. |
| **GitHub Repositories** | PARTIAL | Frontend sends `personal_access_token`, connector checked `access_token`; missing `_is_prohibited_path` method; secret stripping incomplete. | Support `personal_access_token`; implement `_is_prohibited_path` with extended secret patterns; support incremental sync metadata. |
| **Google Drive** | PARTIAL / SETUP REQUIRED | Frontend missing `access_token` input; binary files downloaded as `.text`; lack of Google Docs export parsing. | Add OAuth/token input in UI; handle binary downloads with proper parsers; provide actionable setup instructions. |
| **Notion** | PARTIAL | Frontend sends `integration_token`, connector only checked `api_key`/`token`; missing block pagination; setup message mismatch. | Support `integration_token`; paginate children blocks; parse database rows into semantic markdown; align test assertions. |
| **PostgreSQL Relational** | PARTIAL | Batching was rudimentary; self-connection check was strict; column selection was missing; table allowlisting needed. | Parameterize SQL; enforce schema/table identifier regex; allow safe self-connect override with read-only credentials; format rows with full column context. |

---

## 4. Database & Infrastructure Bugs Found

1. **Duplicate Index in `models.py`**:
   `DataSource` had `status: Mapped[str] = mapped_column(..., index=True)` and `Index("ix_data_sources_status", "status")` in `__table_args__`. This caused SQLite in-memory test database initialization to fail with `OperationalError: index ix_data_sources_status already exists`.
2. **Missing Python Dependency**:
   `openpyxl` was not installed, though `xlsx_parser.py` was implemented using standard library `zipfile` and `xml.etree.ElementTree`. We will ensure standard library parsing is robust.

---

## 5. Next Steps Plan (Phase 13 Strategy)

1. **Fix Database Model & Parser Bugs**: Remove duplicate index, fix HTML/XLSX/CSV/JSON/DOCX/MD parsers and verify `test_data_sources.py` passes.
2. **Standardize Shared Connector Base**: Ensure all connectors adhere to common contract, parameter aliases, and normalized document schema.
3. **Enhance Website Scraper**: Add robots.txt compliance, rate limiting, size limits, redirect validation, and sitemap crawling.
4. **Enhance GitHub Connector**: Add secret regex filters, repository listing, branch selection, and content extraction.
5. **Enhance Google Drive Connector**: Add token field to UI, binary file handling, Google Docs/Sheets export, and setup guidance.
6. **Enhance Notion Connector**: Support pagination, database querying, markdown conversion, and permission validation.
7. **Enhance PostgreSQL Connector**: Strict identifier validation, parameterized row querying, table allowlisting, and semantic tabular formatting.
8. **Frontend UI Refinements**: Align form field names with backend parameters, show honest status badges, provide clear setup guides.
9. **End-to-End Testing**: Run complete automated test suite verifying ingestion, embeddings, search, citations, and error recovery.
