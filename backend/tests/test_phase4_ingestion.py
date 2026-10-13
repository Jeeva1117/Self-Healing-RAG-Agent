"""Phase 4 targeted tests covering upload, validation, parsing, error recovery, security, and persistence."""

import io
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from pypdf import PdfWriter
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import User
from app.services.ingestion_service import IngestionService
from app.services.parsers.pdf_parser import PDFParser


def create_text_pdf(text: str = "This is a valid test PDF document content.") -> bytes:
    """Creates a basic PDF with text in-memory."""
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_metadata({"/Title": "Phase 4 Test PDF"})
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_unauthenticated_upload_rejection(client: AsyncClient):
    """Unauthenticated upload request must be rejected with 401."""
    random_kb_id = uuid4()
    files = {"file": ("test.txt", io.BytesIO(b"content"), "text/plain")}
    res = await client.post(f"/api/v1/knowledge-bases/{random_kb_id}/documents", files=files)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_upload_to_another_users_kb_rejected(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
):
    """User B cannot upload to User A's Knowledge Base (rejected with 404/access denied)."""
    # User A creates a KB
    res_kb = await client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Alice Private KB"},
        headers=auth_headers_user_a,
    )
    assert res_kb.status_code == 201
    kb_id = res_kb.json()["data"]["id"]

    # User B attempts to upload a document to User A's KB
    files = {"file": ("doc.txt", io.BytesIO(b"Unauthorized file content"), "text/plain")}
    res = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        files=files,
        headers=auth_headers_user_b,
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "KNOWLEDGE_BASE_NOT_FOUND"


@pytest.mark.asyncio
async def test_oversized_file_rejected(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
):
    """Uploading a file exceeding MAX_UPLOAD_SIZE_MB is rejected with 413."""
    res_kb = await client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Size Test KB"},
        headers=auth_headers_user_a,
    )
    kb_id = res_kb.json()["data"]["id"]

    # Patch MAX_UPLOAD_SIZE_MB to 1MB for the test
    with patch("app.services.ingestion_service.settings.MAX_UPLOAD_SIZE_MB", 1):
        big_bytes = b"X" * (2 * 1024 * 1024)  # 2MB
        files = {"file": ("big.txt", io.BytesIO(big_bytes), "text/plain")}
        res = await client.post(
            f"/api/v1/knowledge-bases/{kb_id}/documents",
            files=files,
            headers=auth_headers_user_a,
        )
        assert res.status_code == 413
        assert res.json()["error"]["code"] == "FILE_TOO_LARGE"


@pytest.mark.asyncio
async def test_malformed_pdf_parser_failure(
    db_session: AsyncSession,
    user_a: User,
):
    """Malformed/corrupted PDF bytes result in parsed_doc.error and FAILED status."""
    corrupted_bytes = b"%PDF-1.4 completely corrupt content not a real pdf"
    parser = PDFParser()
    parsed = parser.parse(corrupted_bytes, "corrupt.pdf")
    assert parsed.error is not None
    assert "CORRUPT_OR_INVALID_PDF" in parsed.error


@pytest.mark.asyncio
async def test_scanned_pdf_detects_ocr_required(
    db_session: AsyncSession,
    user_a: User,
):
    """PDF with pages but under 20 chars of text triggers is_scanned and OCR_REQUIRED status."""
    # Blank PDF has pages but 0 text
    blank_pdf = create_text_pdf()
    parser = PDFParser()
    parsed = parser.parse(blank_pdf, "scanned.pdf")
    assert parsed.is_scanned is True
    assert "OCR is required" in (parsed.error or "")


@pytest.mark.asyncio
async def test_embedding_provider_outage_marks_document_failed(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    db_session: AsyncSession,
):
    """When embedding provider raises an unhandled exception, document status becomes FAILED."""
    res_kb = await client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Outage Test KB"},
        headers=auth_headers_user_a,
    )
    kb_id = res_kb.json()["data"]["id"]

    files = {"file": ("test_doc.txt", io.BytesIO(b"Sample text content for embedding failure."), "text/plain")}
    res = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        files=files,
        headers=auth_headers_user_a,
    )
    assert res.status_code == 202
    doc_id = UUID(res.json()["data"]["id"])

    # Instantiate ingestion service with failing embedding mock
    mock_embeddings = AsyncMock()
    mock_embeddings.dimension = 384
    mock_embeddings.model_name = "mock-model"
    mock_embeddings.provider_name = "mock"
    mock_embeddings.embed_documents.side_effect = RuntimeError("Embedding provider 503 service unavailable")

    ingestion = IngestionService(db_session, embedding_provider=mock_embeddings)
    await ingestion.run_ingestion_pipeline(doc_id)

    # Verify document is FAILED with error message recorded
    doc_res = await client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers_user_a)
    assert doc_res.status_code == 200
    doc_data = doc_res.json()["data"]
    assert doc_data["status"] == "FAILED"
    assert "Embedding provider 503" in (doc_data["ingestion_error"] or "")


@pytest.mark.asyncio
async def test_cross_user_document_security(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    db_session: AsyncSession,
):
    """User B cannot GET, download, view chunks, or delete User A's document."""
    # User A creates KB and uploads document
    res_kb = await client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Alice KB"},
        headers=auth_headers_user_a,
    )
    kb_id = res_kb.json()["data"]["id"]

    files = {"file": ("secret.txt", io.BytesIO(b"Confidential data"), "text/plain")}
    res_upload = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        files=files,
        headers=auth_headers_user_a,
    )
    doc_id = res_upload.json()["data"]["id"]

    # 1. User B tries GET /documents/{id}
    res_b_get = await client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers_user_b)
    assert res_b_get.status_code == 404

    # 2. User B tries GET /documents/{id}/download
    res_b_dl = await client.get(f"/api/v1/documents/{doc_id}/download", headers=auth_headers_user_b)
    assert res_b_dl.status_code == 404

    # 3. User B tries GET /documents/{id}/chunks
    res_b_chunks = await client.get(f"/api/v1/documents/{doc_id}/chunks", headers=auth_headers_user_b)
    assert res_b_chunks.status_code == 404

    # 4. User B tries DELETE /documents/{id}
    res_b_del = await client.delete(f"/api/v1/documents/{doc_id}", headers=auth_headers_user_b)
    assert res_b_del.status_code == 404


@pytest.mark.asyncio
async def test_document_download_flow(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
):
    """User A can download their uploaded document and verify content and headers match."""
    res_kb = await client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Download KB"},
        headers=auth_headers_user_a,
    )
    kb_id = res_kb.json()["data"]["id"]

    original_bytes = b"The exact content of the uploaded document to be downloaded."
    files = {"file": ("report.txt", io.BytesIO(original_bytes), "text/plain")}
    res_upload = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        files=files,
        headers=auth_headers_user_a,
    )
    doc_id = res_upload.json()["data"]["id"]

    # Download document
    res_dl = await client.get(f"/api/v1/documents/{doc_id}/download", headers=auth_headers_user_a)
    assert res_dl.status_code == 200
    assert res_dl.content == original_bytes
    assert 'attachment; filename="report.txt"' in res_dl.headers.get("content-disposition", "")
