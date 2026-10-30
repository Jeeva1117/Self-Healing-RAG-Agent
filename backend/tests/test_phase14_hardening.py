"""Phase 14 targeted regression tests for security invariants, streaming bounds, and reliability safeguards."""

import io
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ValidationError
from app.infrastructure.database.models import User
from app.infrastructure.storage.local_storage import LocalStorageProvider
from app.services.ingestion_service import IngestionService
from app.services.observability.schemas import TraceRecord
from app.services.observability.service import ObservabilityService


def test_production_config_rejects_insecure_jwt_secret():
    """In production mode, default or weak JWT_SECRET must raise a configuration validation error."""
    with pytest.raises(PydanticValidationError) as exc_info:
        Settings(
            APP_ENV="production",
            JWT_SECRET="phase1-production-foundation-insecure-secret-key-change-me",
        )
    assert "CRITICAL SECURITY CONFIGURATION ERROR: JWT_SECRET" in str(exc_info.value)


def test_production_config_enforces_cookie_secure():
    """In production mode with a valid secure secret, COOKIE_SECURE is automatically enforced to True."""
    s = Settings(
        APP_ENV="production",
        JWT_SECRET="super-strong-production-cryptographic-signing-key-32chars",
        COOKIE_SECURE=False,
    )
    assert s.COOKIE_SECURE is True


def test_staging_config_enforces_cookie_secure():
    """In staging mode, COOKIE_SECURE is automatically enforced to True."""
    s = Settings(
        APP_ENV="staging",
        JWT_SECRET="staging-valid-signing-key-minimum-32-chars",
        COOKIE_SECURE=False,
    )
    assert s.COOKIE_SECURE is True


def test_development_config_permits_local_defaults():
    """In development or test mode, default keys are permitted for zero-friction local developer runs."""
    s = Settings(
        APP_ENV="development",
        JWT_SECRET="phase1-production-foundation-insecure-secret-key-change-me",
        COOKIE_SECURE=False,
    )
    assert s.JWT_SECRET == "phase1-production-foundation-insecure-secret-key-change-me"
    assert s.COOKIE_SECURE is False


def test_validation_error_status_code_422():
    """ValidationError uses HTTP 422 cleanly without deprecation warnings."""
    err = ValidationError("Field validation failure", code="INVALID_INPUT")
    assert err.status_code == 422
    assert err.code == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_bounded_upload_size_limit(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
):
    """Uploading a document stream exceeding MAX_UPLOAD_SIZE_MB raises 413 FILE_TOO_LARGE."""
    # 1. Create a Knowledge Base
    res_kb = await client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Streaming Bound KB"},
        headers=auth_headers_user_a,
    )
    assert res_kb.status_code == 201
    kb_id = res_kb.json()["data"]["id"]

    # 2. Patch limit to 1MB and attempt uploading 2MB payload
    with patch("app.api.routes.knowledge_bases.settings.MAX_UPLOAD_SIZE_MB", 1):
        big_stream = io.BytesIO(b"A" * (2 * 1024 * 1024))
        res = await client.post(
            f"/api/v1/knowledge-bases/{kb_id}/documents",
            files={"file": ("stream_large.txt", big_stream, "text/plain")},
            headers=auth_headers_user_a,
        )
        assert res.status_code == 413
        assert res.json()["error"]["code"] == "FILE_TOO_LARGE"


@pytest.mark.asyncio
async def test_storage_cleanup_on_persistence_failure(
    db_session: AsyncSession,
    user_a: User,
):
    """If database record creation fails, the staged file in storage is cleaned up."""
    # Create KB
    from app.infrastructure.database.models import KnowledgeBase

    kb = KnowledgeBase(
        owner_id=user_a.id,
        name="Rollback Test KB",
    )
    db_session.add(kb)
    await db_session.commit()
    await db_session.refresh(kb)

    mock_storage = AsyncMock(spec=LocalStorageProvider)
    service = IngestionService(db_session, storage_provider=mock_storage)

    # Force database failure during document creation
    with patch.object(service.doc_repo, "create", side_effect=RuntimeError("Simulated DB Connection Failure")):
        with pytest.raises(RuntimeError):
            await service.validate_and_create_document(
                kb_id=kb.id,
                user_id=user_a.id,
                filename="test_rollback.txt",
                content_type="text/plain",
                file_bytes=b"Hello test rollback content",
            )

        # Verify storage save was called, followed by storage delete cleanup
        assert mock_storage.save.called
        assert mock_storage.delete.called


@pytest.mark.asyncio
async def test_observability_safe_during_flush():
    """ObservabilityService gracefully skips session.add when session is actively flushing, avoiding SAWarning."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.sync_session = AsyncMock()
    mock_session.sync_session._flushing = True  # Simulating active flush state

    service = ObservabilityService(mock_session)
    trace = TraceRecord(
        trace_id="test-trace-flushing-123",
        query="What is testing?",
        status="completed",
        duration_ms=45.2,
        tokens_total=120,
        model="gpt-4o",
        start_time=1000.0,
        end_time=1045.2,
        created_at=datetime.now(UTC).isoformat(),
    )

    # Should not invoke mock_session.add during active flush
    await service.record_trace(trace)
    assert not mock_session.add.called

    # But trace is still reliably recorded in the in-memory circular buffer
    buffered = (
        ObservabilityService.getBufferedTraces()
        if hasattr(ObservabilityService, "getBufferedTraces")
        else ObservabilityService.get_buffered_traces()
    )
    assert any(t.trace_id == "test-trace-flushing-123" for t in buffered)
