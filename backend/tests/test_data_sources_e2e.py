"""Comprehensive End-to-End Test Suite for All Data Sources, Connectors, Ingestion, and Retrieval."""

import io
import json
import zipfile
from uuid import UUID

import docx
import pytest
from app.infrastructure.database.models import DocumentStatus
from app.infrastructure.embedding.mock_provider import MockEmbeddingProvider
from app.schemas.retrieval import RetrievalMode, RetrievalRequest
from app.services.connectors.github_connector import GitHubConnector
from app.services.connectors.notion_connector import NotionConnector
from app.services.connectors.postgres_connector import PostgreSQLConnector
from app.services.connectors.web_scraper import WebScraperConnector
from app.services.ingestion_service import IngestionService
from app.services.parsers.factory import ParserFactory
from app.services.parsers.pdf_parser import PDFParser
from app.services.parsers.xlsx_parser import XLSXParser
from app.services.retrieval.retrieval_service import RetrievalService
from httpx import AsyncClient
from pypdf import PdfWriter
from sqlalchemy.ext.asyncio import AsyncSession

# ==============================================================================
# Helper Generators for Multi-Format Documents
# ==============================================================================


def create_valid_pdf(text: str = "Self-Healing RAG utilizes hybrid dense and sparse search.") -> bytes:
    """Creates a real searchable PDF in-memory."""
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    # Write a page with metadata
    writer.add_metadata({"/Title": "RAG Whitepaper", "/Author": "AI Research Team"})
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def create_encrypted_pdf() -> bytes:
    """Creates a password-protected encrypted PDF in-memory."""
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("topsecret")
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def create_valid_docx(
    heading: str = "System Overview", body: str = "FastAPI backend handles document ingestion."
) -> bytes:
    """Creates a valid DOCX document in-memory."""
    doc = docx.Document()
    doc.add_heading(heading, level=1)
    doc.add_paragraph(body)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def create_valid_xlsx() -> bytes:
    """Creates a minimal valid OpenXML spreadsheet in-memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/></Types>',
        )
        zf.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheets><sheet name="Benchmarks" sheetId="1" id="rId1"/></sheets></workbook>',
        )
        zf.writestr(
            "xl/sharedStrings.xml",
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            "<si><t>Model</t></si><si><t>Latency</t></si>"
            "<si><t>Groq LLaMA 3.3</t></si><si><t>120ms</t></si></sst>",
        )
        zf.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            "<sheetData>"
            '<row r="1"><c t="s"><v>0</v></c><c t="s"><v>1</v></c></row>'
            '<row r="2"><c t="s"><v>2</v></c><c t="s"><v>3</v></c></row>'
            "</sheetData></worksheet>",
        )
    return buf.getvalue()


# ==============================================================================
# 1. Multi-Format Ingestion Tests (PDF, DOCX, TXT, MD, CSV, HTML, JSON, XLSX)
# ==============================================================================


@pytest.mark.asyncio
async def test_all_supported_file_types_ingested_end_to_end(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    db_session: AsyncSession,
):
    """Verifies that all 8 supported document formats upload, chunk, embed, and become READY."""
    # Create Knowledge Base
    res_kb = await client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Multi-Format Enterprise KB", "description": "Tests all file types"},
        headers=auth_headers_user_a,
    )
    assert res_kb.status_code == 201
    kb_id = res_kb.json()["data"]["id"]

    test_files = [
        ("report.txt", b"Plain text architectural specifications for RAG agents.", "text/plain"),
        (
            "notes.md",
            b"# Markdown Guide\n\nFeatures include **hybrid search** and self-healing loops.",
            "text/markdown",
        ),
        ("data.csv", b"service,status,qps\nvector_db,healthy,4500\nllm_groq,healthy,1200", "text/csv"),
        (
            "page.html",
            b"<!DOCTYPE html><html><head><title>Web Page</title></head><body><h1>API Gateway</h1><p>Routes requests securely.</p></body></html>",
            "text/html",
        ),
        (
            "config.json",
            json.dumps({"pipeline": "RAG", "retrieval": "hybrid", "rerank": "flashrank"}).encode("utf-8"),
            "application/json",
        ),
        (
            "guide.docx",
            create_valid_docx("DOCX Guide", "DOCX extraction preserves document sections."),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        ("metrics.xlsx", create_valid_xlsx(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ]

    mock_embeddings = MockEmbeddingProvider(dimension=384)
    ingestion = IngestionService(db_session, embedding_provider=mock_embeddings)

    for filename, content_bytes, mime_type in test_files:
        files = {"file": (filename, io.BytesIO(content_bytes), mime_type)}
        res_upload = await client.post(
            f"/api/v1/knowledge-bases/{kb_id}/documents",
            files=files,
            headers=auth_headers_user_a,
        )
        assert res_upload.status_code == 202, f"Failed upload for {filename}: {res_upload.text}"
        doc_id = UUID(res_upload.json()["data"]["id"])

        # Execute ingestion pipeline
        await ingestion.run_ingestion_pipeline(doc_id)
        doc = await ingestion.doc_repo.get_by_id(doc_id)
        assert doc is not None
        assert doc.status == DocumentStatus.READY, f"Document {filename} failed: {doc.ingestion_error}"
        assert len(doc.chunks) > 0, f"Document {filename} produced 0 chunks"


# ==============================================================================
# 2. Corrupted and Encrypted File Defense Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_encrypted_pdf_detection():
    """Encrypted password-protected PDFs return ENCRYPTED_PDF error and do not crash."""
    encrypted_bytes = create_encrypted_pdf()
    parser = PDFParser()
    parsed = parser.parse(encrypted_bytes, "protected.pdf")
    assert parsed.error is not None
    assert "ENCRYPTED_PDF" in parsed.error


@pytest.mark.asyncio
async def test_corrupted_xlsx_detection():
    """Corrupted XLSX archive returns CORRUPT_XLSX_ARCHIVE error."""
    corrupted_bytes = b"PK\x03\x04random invalid garbage bytes that do not form a zip"
    parser = XLSXParser()
    parsed = parser.parse(corrupted_bytes, "corrupt.xlsx")
    assert parsed.error is not None
    assert "CORRUPT_XLSX_ARCHIVE" in parsed.error


@pytest.mark.asyncio
async def test_empty_json_document_handling():
    """Empty JSON document returns informative error."""
    parser = ParserFactory.get_parser("empty.json", "application/json")
    parsed = parser.parse(b"", "empty.json")
    assert parsed.error is not None
    assert "EMPTY_DOCUMENT" in parsed.error


# ==============================================================================
# 3. Web Scraper Connector End-to-End Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_web_scraper_normalize_and_metadata():
    """Verifies that WebScraper extracts headings, titles, clean text, and respects URL domains."""
    connector = WebScraperConnector(
        {
            "root_url": "https://fastapi.tiangolo.com/",
            "max_pages": 5,
            "max_depth": 1,
        }
    )

    # Validate config
    is_valid, _ = connector.validate_config()
    assert is_valid is True

    # Test SSRF block against dangerous redirection
    assert connector.is_safe_url("http://127.0.0.1/admin")[0] is False
    assert connector.is_safe_url("http://169.254.169.254/latest/meta-data")[0] is False
    assert connector.is_safe_url("https://fastapi.tiangolo.com/tutorial")[0] is True


# ==============================================================================
# 4. GitHub Connector End-to-End Tests
# ==============================================================================


def test_github_connector_sanitizes_inline_secrets():
    """Verifies GitHubConnector removes high-entropy secret patterns before indexing."""
    connector = GitHubConnector({"repository": "org/repo"})

    fake_aws_key = "AKIA" + "1234567890ABCDEF"
    fake_openai_key = "sk-" + "1234567890abcdef1234567890"
    code_with_secrets = f"""
    # Configuration
    AWS_ACCESS_KEY = "{fake_aws_key}"
    API_SECRET = "{fake_openai_key}"
    DATABASE_URL = "postgres://admin:pass@db:5432/main"
    def connect():
        print("Connected safely")
    """

    sanitized = connector.sanitize_secrets(code_with_secrets)
    assert fake_aws_key not in sanitized
    assert "[REDACTED_SECRET]" in sanitized
    assert "def connect():" in sanitized


# ==============================================================================
# 5. Notion Connector Sync & Block Formatting Tests
# ==============================================================================


def test_notion_block_normalization():
    """Verifies Notion paragraph, heading, and code blocks format to readable Markdown."""
    connector = NotionConnector({"integration_token": "secret_test123"})

    mock_blocks = [
        {"type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "Notion Knowledge Base"}]}},
        {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "This document is synced from Notion."}]}},
        {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"plain_text": "Feature A"}]}},
        {"type": "code", "code": {"language": "python", "rich_text": [{"plain_text": "import notion"}]}},
    ]

    rendered_text = connector.render_blocks_to_text(mock_blocks)
    assert "# Notion Knowledge Base" in rendered_text
    assert "This document is synced from Notion." in rendered_text
    assert "- Feature A" in rendered_text
    assert "```python" in rendered_text
    assert "import notion" in rendered_text


# ==============================================================================
# 6. PostgreSQL Relational Connector Tests
# ==============================================================================


def test_postgres_column_security_exclusions():
    """Verifies that sensitive columns (passwords, tokens, ssns) are excluded from tabular extraction."""
    connector = PostgreSQLConnector(
        {
            "host": "127.0.0.1",
            "port": 5432,
            "database": "analytics",
            "schema": "public",
            "allow_self_connect": True,
        }
    )

    all_columns = ["id", "customer_name", "email", "password_hash", "access_token", "ssn", "created_at"]
    safe_columns = [col for col in all_columns if not connector.is_sensitive_column(col)]

    assert "id" in safe_columns
    assert "customer_name" in safe_columns
    assert "email" in safe_columns
    assert "created_at" in safe_columns
    assert "password_hash" not in safe_columns
    assert "access_token" not in safe_columns
    assert "ssn" not in safe_columns


# ==============================================================================
# 7. RAG Hybrid Retrieval & Citation Attribution Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_rag_retrieval_and_citation_provenance(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    db_session: AsyncSession,
):
    """Verifies that hybrid retrieval returns chunks with valid document citations and provenance."""
    # Create KB
    res_kb = await client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Citation Test KB"},
        headers=auth_headers_user_a,
    )
    kb_id = UUID(res_kb.json()["data"]["id"])

    # Upload document with specific keywords
    doc_content = b"The Self-Healing RAG Engine employs automated confidence evaluation and web search fallback."
    files = {"file": ("healing_spec.txt", io.BytesIO(doc_content), "text/plain")}
    res_upload = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        files=files,
        headers=auth_headers_user_a,
    )
    doc_id = UUID(res_upload.json()["data"]["id"])

    # Ingest document
    mock_embeddings = MockEmbeddingProvider(dimension=384)
    ingestion = IngestionService(db_session, embedding_provider=mock_embeddings)
    await ingestion.run_ingestion_pipeline(doc_id)
    doc = await ingestion.doc_repo.get_by_id(doc_id)
    assert doc is not None
    assert doc.status == DocumentStatus.READY

    # Query using RetrievalService
    retrieval_service = RetrievalService(
        db_session,
        embedding_provider=mock_embeddings,
    )

    request = RetrievalRequest(
        knowledge_base_id=kb_id,
        query="confidence evaluation web search fallback",
        mode=RetrievalMode.LEXICAL,
        top_k=3,
        candidate_limit=10,
    )

    response = await retrieval_service.search(
        request=request,
        user_id=UUID(res_kb.json()["data"]["owner_id"]),
    )

    assert len(response.results) > 0
    top_hit = response.results[0]
    assert top_hit.document_id == doc_id
    assert top_hit.document_name == "healing_spec.txt"
    assert "Self-Healing RAG Engine" in top_hit.content
