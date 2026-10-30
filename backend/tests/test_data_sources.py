"""Comprehensive automated test suite for Data Sources, Parsers, and External Connectors."""

import pytest
from app.schemas.data_source import mask_sensitive_config
from app.services.connectors.gdrive_connector import GoogleDriveConnector
from app.services.connectors.github_connector import GitHubConnector
from app.services.connectors.notion_connector import NotionConnector
from app.services.connectors.postgres_connector import SQL_IDENTIFIER_PATTERN, PostgreSQLConnector
from app.services.connectors.web_scraper import WebScraperConnector
from app.services.parsers.factory import ParserFactory
from app.services.parsers.html_parser import HTMLDocumentParser
from app.services.parsers.json_parser import JSONParser
from app.services.parsers.xlsx_parser import XLSXParser

# ==============================================================================
# PHASE 3: Parser Tests (HTML, JSON, XLSX, Factory)
# ==============================================================================


def test_parser_factory_supports_all_file_types():
    """Verifies that ParserFactory returns valid parsers for all 9 supported extensions."""
    supported_extensions = ["pdf", "docx", "txt", "md", "csv", "html", "htm", "json", "xlsx"]
    for ext in supported_extensions:
        filename = f"sample_document.{ext}"
        parser = ParserFactory.get_parser(filename=filename, content_type=None)
        assert parser is not None, f"ParserFactory failed for extension .{ext}"


def test_html_parser_cleans_tags_and_scripts():
    """Verifies HTML parser extracts meaningful text while stripping scripts, styles, and boilerplate."""
    html_content = b"""
    <!DOCTYPE html>
    <html>
    <head><title>Technical Architecture Guide</title><style>body { color: red; }</style></head>
    <body>
        <script>console.log("malicious code");</script>
        <h1>System Overview</h1>
        <p>The Self-Healing RAG Agent provides automated recovery from hallucination.</p>
        <p>Secondary paragraph with architectural details.</p>
    </body>
    </html>
    """
    parser = HTMLDocumentParser()
    parsed = parser.parse(html_content, "guide.html")
    assert parsed.error is None
    assert len(parsed.units) > 0
    full_text = parsed.full_text
    assert "Technical Architecture Guide" in full_text
    assert "System Overview" in full_text
    assert "Self-Healing RAG Agent" in full_text
    assert "malicious code" not in full_text
    assert "body { color: red; }" not in full_text


def test_json_parser_formats_structured_content():
    """Verifies JSON parser structures keys and values into readable context."""
    json_bytes = b'{"service": "RAG Engine", "version": "2.0", "features": ["pgvector", "Groq LLM", "LangGraph"]}'
    parser = JSONParser()
    parsed = parser.parse(json_bytes, "config.json")
    assert parsed.error is None
    full_text = parsed.full_text
    assert "service: RAG Engine" in full_text
    assert "version: 2.0" in full_text
    assert "pgvector" in full_text


def test_xlsx_parser_handles_empty_or_corrupt_files():
    """Verifies safe error handling for invalid or corrupted spreadsheet archives."""
    parser = XLSXParser()
    parsed = parser.parse(b"corrupted_garbage_bytes", "report.xlsx")
    assert parsed.error is not None
    assert "CORRUPT_XLSX_ARCHIVE" in parsed.error


# ==============================================================================
# PHASE 4: Web Scraper & SSRF Protection Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_web_scraper_ssrf_protection():
    """Verifies that SSRF validator strictly blocks private, loopback, and metadata addresses."""
    # Loopback targets
    connector_localhost = WebScraperConnector({"root_url": "http://127.0.0.1:8000"})
    res_loopback = await connector_localhost.test_connection()
    assert res_loopback.success is False
    assert "private" in res_loopback.message.lower() or "loopback" in res_loopback.message.lower()

    # Cloud metadata target
    connector_metadata = WebScraperConnector({"root_url": "http://169.254.169.254/latest/meta-data/"})
    res_meta = await connector_metadata.test_connection()
    assert res_meta.success is False
    assert "metadata" in res_meta.message.lower() or "private" in res_meta.message.lower()

    # Private RFC 1918 target
    connector_private = WebScraperConnector({"root_url": "http://10.0.0.1/admin"})
    res_priv = await connector_private.test_connection()
    assert res_priv.success is False

    # Non-HTTP protocol
    connector_file = WebScraperConnector({"root_url": "file:///etc/passwd"})
    res_file = await connector_file.test_connection()
    assert res_file.success is False


# ==============================================================================
# PHASE 5: GitHub Connector & Secret Stripping Tests
# ==============================================================================


def test_github_connector_filters_secrets_and_binaries():
    """Verifies GitHub connector excludes credential files and compiled binaries."""
    connector = GitHubConnector({"repository": "owner/repo"})

    # Prohibited secret files
    assert connector._is_prohibited_path(".env") is True
    assert connector._is_prohibited_path("config/.env.production") is True
    assert connector._is_prohibited_path("certs/server.key") is True
    assert connector._is_prohibited_path("keys/id_rsa") is True
    assert connector._is_prohibited_path("secrets/jwt_secret.pem") is True
    assert connector._is_prohibited_path("node_modules/package/index.js") is True

    # Permitted documentation and code files
    assert connector._is_prohibited_path("README.md") is False
    assert connector._is_prohibited_path("docs/architecture.md") is False
    assert connector._is_prohibited_path("src/main.py") is False
    assert connector._is_prohibited_path("app/services/retrieval.ts") is False


# ==============================================================================
# PHASE 6: Google Drive Prerequisite Handling Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_google_drive_setup_required_guidance():
    """Verifies honest Setup Required status when OAuth/Service credentials are not yet configured."""
    connector = GoogleDriveConnector({})
    res = await connector.test_connection()
    assert res.success is False
    assert "Setup Required" in res.message or "prerequisite" in res.message.lower()
    assert "drive.readonly" in res.message


# ==============================================================================
# PHASE 7: Notion Token Validation Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_notion_connector_missing_token():
    """Verifies clear setup instructions when Notion integration secret is omitted."""
    connector = NotionConnector({})
    res = await connector.test_connection()
    assert res.success is False
    assert "Setup Required" in res.message
    assert "notion.so/my-integrations" in res.message


# ==============================================================================
# PHASE 8: PostgreSQL Connector Security & SQL Injection Tests
# ==============================================================================


def test_postgres_sql_injection_defense():
    """Verifies SQL identifier regex prevents injection through table and schema names."""
    # Valid identifiers
    assert bool(SQL_IDENTIFIER_PATTERN.match("users")) is True
    assert bool(SQL_IDENTIFIER_PATTERN.match("order_items_v2")) is True

    # Malicious SQL injection payloads
    assert bool(SQL_IDENTIFIER_PATTERN.match("users; DROP TABLE users;--")) is False
    assert bool(SQL_IDENTIFIER_PATTERN.match("users' OR 1=1--")) is False
    assert bool(SQL_IDENTIFIER_PATTERN.match("users/*comment*/")) is False
    assert bool(SQL_IDENTIFIER_PATTERN.match("users union select * from passwords")) is False


def test_postgres_self_connect_protection():
    """Verifies internal database protection prevents self-connection."""
    connector = PostgreSQLConnector(
        {
            "host": "127.0.0.1",
            "port": 5432,
            "database": "self_healing_rag",
            "allow_self_connect": False,
        }
    )
    assert connector._is_self_connection() is True


# ==============================================================================
# SENSITIVE CONFIG MASKING TESTS
# ==============================================================================


def test_sensitive_config_masking():
    """Verifies that API tokens and passwords are masked before returning to UI."""
    raw_config = {
        "repository": "facebook/react",
        "personal_access_token": "mock_github_pat_token_secret_12345",
        "password": "super_secret_db_password",
        "api_key": "mock_test_api_key_12345",
    }
    masked = mask_sensitive_config(raw_config)
    assert masked["repository"] == "facebook/react"
    assert "..." in masked["personal_access_token"]
    assert "..." in masked["password"]
    assert "super_secret_db_password" not in str(masked)
