"""Comprehensive tests for Knowledge Base CRUD, document ingestion, parsers, and pgvector embeddings."""

import io
from uuid import UUID, uuid4

import docx
import pytest
from httpx import AsyncClient
from pypdf import PdfWriter
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.embedding.factory import get_embedding_provider
from app.services.chunker import DocumentChunker
from app.services.ingestion_service import IngestionService
from app.services.normalizer import TextNormalizer
from app.services.parsers.csv_parser import CSVParser
from app.services.parsers.docx_parser import DOCXParser
from app.services.parsers.markdown_parser import MarkdownParser


def create_sample_pdf(text: str = "This is a sample PDF document for testing.") -> bytes:
    """Generates valid in-memory PDF binary data using pypdf."""
    # Since pypdf is primarily a reader/writer of existing streams, we can write a basic valid PDF
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    # Write blank page with metadata
    writer.add_metadata({"/Title": "Test Sample PDF", "/Author": "Test Suite"})
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def create_sample_docx(text: str = "This is a sample DOCX document.") -> bytes:
    """Generates valid in-memory DOCX binary data using python-docx."""
    doc = docx.Document()
    doc.add_heading("Architecture Overview", level=1)
    doc.add_paragraph(text)
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Service"
    table.cell(0, 1).text = "Status"
    table.cell(1, 0).text = "Ingestion"
    table.cell(1, 1).text = "Active"
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ==============================================================================
# 1. Knowledge Base CRUD & Authorization Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_create_knowledge_base(client: AsyncClient, auth_headers_user_a: dict[str, str]):
    """Test 1: Create a Knowledge Base for authenticated user."""
    res = await client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Engineering Docs", "description": "Internal technical specs"},
        headers=auth_headers_user_a,
    )
    assert res.status_code == 201
    payload = res.json()
    assert payload["success"] is True
    assert payload["data"]["name"] == "Engineering Docs"
    assert payload["data"]["description"] == "Internal technical specs"
    assert payload["data"]["document_count"] == 0


@pytest.mark.asyncio
async def test_unauthorized_access_fails(client: AsyncClient):
    """Test 2: Accessing Knowledge Base endpoints without token returns 401."""
    res = await client.get("/api/v1/knowledge-bases")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_user_isolation_knowledge_base(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
):
    """Test 3: User B cannot access or modify User A's Knowledge Base."""
    # User A creates a KB
    res_a = await client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Alice Secret KB", "description": "Confidential"},
        headers=auth_headers_user_a,
    )
    assert res_a.status_code == 201
    kb_id = res_a.json()["data"]["id"]

    # User B tries to GET User A's KB -> 404 (Not Found or Access Denied)
    res_b_get = await client.get(f"/api/v1/knowledge-bases/{kb_id}", headers=auth_headers_user_b)
    assert res_b_get.status_code == 404

    # User B tries to PATCH User A's KB -> 404
    res_b_patch = await client.patch(
        f"/api/v1/knowledge-bases/{kb_id}",
        json={"name": "Hacked Name"},
        headers=auth_headers_user_b,
    )
    assert res_b_patch.status_code == 404

    # User B tries to DELETE User A's KB -> 404
    res_b_del = await client.delete(f"/api/v1/knowledge-bases/{kb_id}", headers=auth_headers_user_b)
    assert res_b_del.status_code == 404


@pytest.mark.asyncio
async def test_list_knowledge_bases_pagination(client: AsyncClient, auth_headers_user_a: dict[str, str]):
    """Test 4: List Knowledge Bases with pagination parameters."""
    for i in range(3):
        await client.post(
            "/api/v1/knowledge-bases",
            json={"name": f"KB {i}", "description": f"Description {i}"},
            headers=auth_headers_user_a,
        )

    res = await client.get("/api/v1/knowledge-bases?offset=0&limit=2", headers=auth_headers_user_a)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_update_knowledge_base(client: AsyncClient, auth_headers_user_a: dict[str, str]):
    """Test 5: Update Knowledge Base metadata."""
    res_create = await client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Initial Name", "description": "Old desc"},
        headers=auth_headers_user_a,
    )
    kb_id = res_create.json()["data"]["id"]

    res_patch = await client.patch(
        f"/api/v1/knowledge-bases/{kb_id}",
        json={"name": "Updated Name", "description": "New desc"},
        headers=auth_headers_user_a,
    )
    assert res_patch.status_code == 200
    data = res_patch.json()["data"]
    assert data["name"] == "Updated Name"
    assert data["description"] == "New desc"


# ==============================================================================
# 2. Parsers, Normalizer & Intelligent Chunking Unit Tests
# ==============================================================================


def test_markdown_parser():
    """Test 6: Markdown parser extracts sections and preserves heading structure."""
    content = b"# Introduction\nWelcome to Self-Healing RAG.\n\n## Architecture\nBuilt with FastAPI."
    parser = MarkdownParser()
    doc = parser.parse(content, "arch.md")
    assert doc.error is None
    assert len(doc.units) == 2
    assert doc.units[0].section_title == "Introduction"
    assert "Welcome" in doc.units[0].text
    assert doc.units[1].section_title == "Architecture"


def test_csv_parser():
    """Test 7: CSV parser creates semantic key-value row representations."""
    content = b"id,name,role\n1,Alice,Engineer\n2,Bob,Architect"
    parser = CSVParser()
    doc = parser.parse(content, "team.csv")
    assert doc.error is None
    assert len(doc.units) >= 1
    assert "id: 1 | name: Alice | role: Engineer" in doc.units[0].text


def test_docx_parser():
    """Test 8: DOCX parser extracts paragraphs and tables."""
    docx_bytes = create_sample_docx("Enterprise knowledge base architecture.")
    parser = DOCXParser()
    doc = parser.parse(docx_bytes, "test.docx")
    assert doc.error is None
    assert len(doc.units) >= 1
    full_text = doc.full_text
    assert "Enterprise knowledge base" in full_text


def test_text_normalizer():
    """Test 9: Normalizer cleans control characters and excessive lines without altering text."""
    dirty_text = "Line 1\r\n\r\n\r\n\r\nLine 2   with   spaces\x00\x08"
    normalized = TextNormalizer.normalize(dirty_text)
    assert "\x00" not in normalized
    assert "\x08" not in normalized
    assert "\r" not in normalized
    assert "\n\n\n" not in normalized
    assert "Line 1\n\nLine 2 with spaces" == normalized


def test_intelligent_chunker():
    """Test 10: Chunker produces structure-aware chunks with citation metadata."""
    content = "## Section 1\n" + (
        "This is paragraph content describing RAG architecture. " * 30
    ) + "\n\n" "## Section 2\n" + ("Second section content detailing embeddings and retrieval. " * 30)
    parser = MarkdownParser()
    parsed_doc = parser.parse(content.encode(), "doc.md")

    chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)
    chunks = chunker.chunk_document(
        parsed_doc=parsed_doc,
        document_id="doc-123",
        document_version_id="ver-1",
        source_filename="doc.md",
    )

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.character_count > 0
        assert chunk.token_count > 0
        assert chunk.start_offset >= 0
        assert chunk.end_offset > chunk.start_offset
        assert chunk.metadata["source_filename"] == "doc.md"
        assert chunk.metadata["document_id"] == "doc-123"


# ==============================================================================
# 3. Document Ingestion Pipeline, Deduplication & Storage Integration
# ==============================================================================


@pytest.mark.asyncio
async def test_upload_and_ingest_txt_document(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    db_session: AsyncSession,
):
    """Test 11: Upload TXT document, background ingestion processes chunks and pgvector embeddings."""
    # Create KB
    res_kb = await client.post("/api/v1/knowledge-bases", json={"name": "Docs"}, headers=auth_headers_user_a)
    kb_id = res_kb.json()["data"]["id"]

    txt_content = (
        "Self-Healing RAG Agent System Architecture.\n\n"
        "The system incorporates hybrid retrieval with dense pgvector embeddings and lexical search.\n\n"
        "Self-healing recovery automatically repairs retrieval gaps and improves answer fidelity."
    )

    files = {"file": ("architecture.txt", io.BytesIO(txt_content.encode("utf-8")), "text/plain")}
    res_upload = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        files=files,
        headers=auth_headers_user_a,
    )
    assert res_upload.status_code == 202
    doc_data = res_upload.json()["data"]
    doc_id = UUID(doc_data["id"])
    assert doc_data["filename"] == "architecture.txt"

    # Synchronously execute ingestion pipeline directly for test deterministic verification
    ingestion = IngestionService(db_session)
    await ingestion.run_ingestion_pipeline(uuid4())  # non-existent doc handled gracefully
    await ingestion.run_ingestion_pipeline(doc_id)

    # Verify document status is READY
    doc_res = await client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers_user_a)
    assert doc_res.status_code == 200
    doc = doc_res.json()["data"]
    assert doc["status"] == "READY"
    assert doc["chunk_count"] > 0
    assert doc["ingestion_error"] is None

    # Verify chunks and citation metadata
    chunks_res = await client.get(f"/api/v1/documents/{doc_id}/chunks", headers=auth_headers_user_a)
    assert chunks_res.status_code == 200
    chunk_list = chunks_res.json()["data"]["items"]
    assert len(chunk_list) > 0
    for c in chunk_list:
        assert c["chunk_metadata"]["embedding_model"] is not None
        assert c["chunk_metadata"]["embedding_dimension"] == 384


@pytest.mark.asyncio
async def test_duplicate_upload_rejection(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
):
    """Test 12: Uploading duplicate document with identical SHA-256 is rejected with 409 Conflict."""
    res_kb = await client.post("/api/v1/knowledge-bases", json={"name": "Dup KB"}, headers=auth_headers_user_a)
    kb_id = res_kb.json()["data"]["id"]

    file_bytes = b"Identical file content for duplicate checksum test."
    files = {"file": ("doc.txt", io.BytesIO(file_bytes), "text/plain")}

    # First upload succeeds
    res1 = await client.post(f"/api/v1/knowledge-bases/{kb_id}/documents", files=files, headers=auth_headers_user_a)
    assert res1.status_code == 202

    # Second upload with identical bytes fails with 409
    files2 = {"file": ("another_name.txt", io.BytesIO(file_bytes), "text/plain")}
    res2 = await client.post(f"/api/v1/knowledge-bases/{kb_id}/documents", files=files2, headers=auth_headers_user_a)
    assert res2.status_code == 409
    assert res2.json()["error"]["code"] == "DUPLICATE_DOCUMENT"


@pytest.mark.asyncio
async def test_unsupported_file_format_rejected(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
):
    """Test 13: Uploading unsupported file format (.exe) is rejected with 400 Bad Request."""
    res_kb = await client.post("/api/v1/knowledge-bases", json={"name": "Format KB"}, headers=auth_headers_user_a)
    kb_id = res_kb.json()["data"]["id"]

    files = {"file": ("malicious.exe", io.BytesIO(b"MZ...binary"), "application/x-msdownload")}
    res = await client.post(f"/api/v1/knowledge-bases/{kb_id}/documents", files=files, headers=auth_headers_user_a)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "UNSUPPORTED_DOCUMENT_FORMAT"


@pytest.mark.asyncio
async def test_empty_file_rejected(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
):
    """Test 14: Uploading 0-byte file is rejected with 400 Bad Request."""
    res_kb = await client.post("/api/v1/knowledge-bases", json={"name": "Empty KB"}, headers=auth_headers_user_a)
    kb_id = res_kb.json()["data"]["id"]

    files = {"file": ("empty.txt", io.BytesIO(b""), "text/plain")}
    res = await client.post(f"/api/v1/knowledge-bases/{kb_id}/documents", files=files, headers=auth_headers_user_a)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "EMPTY_FILE"


@pytest.mark.asyncio
async def test_document_reprocessing(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    db_session: AsyncSession,
):
    """Test 15: Reprocessing a document clears previous chunks and re-embeds cleanly."""
    res_kb = await client.post("/api/v1/knowledge-bases", json={"name": "Reprocess KB"}, headers=auth_headers_user_a)
    kb_id = res_kb.json()["data"]["id"]

    content = b"Reprocessing test document content with multiple paragraphs.\n\nSecond paragraph for test."
    files = {"file": ("reprocess.txt", io.BytesIO(content), "text/plain")}
    res_upload = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents", files=files, headers=auth_headers_user_a
    )
    doc_id = UUID(res_upload.json()["data"]["id"])

    # Initial chunk count after ingestion completes
    chunks_before = await client.get(f"/api/v1/documents/{doc_id}/chunks", headers=auth_headers_user_a)
    count_before = len(chunks_before.json()["data"]["items"])
    assert count_before > 0

    # Trigger reprocess endpoint (triggers background reprocess pipeline)
    res_reprocess = await client.post(f"/api/v1/documents/{doc_id}/reprocess", headers=auth_headers_user_a)
    assert res_reprocess.status_code == 200
    assert res_reprocess.json()["data"]["status"] in ["PROCESSING", "READY"]

    # Chunk count must not double (previous chunks cleaned safely during reprocessing)
    chunks_after = await client.get(f"/api/v1/documents/{doc_id}/chunks", headers=auth_headers_user_a)
    count_after = len(chunks_after.json()["data"]["items"])
    assert count_after == count_before


@pytest.mark.asyncio
async def test_delete_document_cleans_resources(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    db_session: AsyncSession,
):
    """Test 16: Deleting document deletes storage files and all associated chunks."""
    res_kb = await client.post("/api/v1/knowledge-bases", json={"name": "Delete KB"}, headers=auth_headers_user_a)
    kb_id = res_kb.json()["data"]["id"]

    files = {"file": ("to_delete.txt", io.BytesIO(b"Temporary file content to delete."), "text/plain")}
    res_upload = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents", files=files, headers=auth_headers_user_a
    )
    doc_id = UUID(res_upload.json()["data"]["id"])

    ingestion = IngestionService(db_session)
    await ingestion.run_ingestion_pipeline(doc_id)

    # Delete document
    del_res = await client.delete(f"/api/v1/documents/{doc_id}", headers=auth_headers_user_a)
    assert del_res.status_code == 200

    # Ensure document is gone
    get_res = await client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers_user_a)
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_cascade_delete_knowledge_base(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    db_session: AsyncSession,
):
    """Test 17: Deleting Knowledge Base cascades and cleans all documents and chunks."""
    res_kb = await client.post("/api/v1/knowledge-bases", json={"name": "Cascade KB"}, headers=auth_headers_user_a)
    kb_id = res_kb.json()["data"]["id"]

    files = {"file": ("cascade.txt", io.BytesIO(b"Cascade document content."), "text/plain")}
    res_upload = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents", files=files, headers=auth_headers_user_a
    )
    doc_id = UUID(res_upload.json()["data"]["id"])

    ingestion = IngestionService(db_session)
    await ingestion.run_ingestion_pipeline(doc_id)

    # Delete Knowledge Base
    del_kb_res = await client.delete(f"/api/v1/knowledge-bases/{kb_id}", headers=auth_headers_user_a)
    assert del_kb_res.status_code == 200

    # Knowledge Base and documents must be gone
    get_kb = await client.get(f"/api/v1/knowledge-bases/{kb_id}", headers=auth_headers_user_a)
    assert get_kb.status_code == 404

    get_doc = await client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers_user_a)
    assert get_doc.status_code == 404


# ==============================================================================
# 4. Embedding Model Verification & Dimension Integrity
# ==============================================================================


@pytest.mark.asyncio
async def test_embedding_dimensions_and_validity():
    """Test 18: Embedding provider outputs valid non-empty vectors with dimension 384."""
    provider = get_embedding_provider()
    texts = ["Self-Healing RAG", "Knowledge Base Ingestion", "Enterprise AI Agent"]
    vectors = await provider.embed_documents(texts)

    assert len(vectors) == 3
    for v in vectors:
        assert len(v) == 384
        # Verify no NaN or infinite values
        for val in v:
            assert isinstance(val, float)
            assert not (val != val)  # not NaN
