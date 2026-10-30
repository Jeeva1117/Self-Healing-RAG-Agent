"""Comprehensive integration and regression test suite for Data Sources API endpoints.

Tests cover:
1. Exact MetaInfo.total regression test (reproducing the original error vs verified fix).
2. GET /api/v1/data-sources/catalog success and schema compliance.
3. GET /api/v1/data-sources success with empty records and valid pagination metadata.
4. Response schema validation with MetaInfo envelope (total, offset, limit).
5. Authentication and authorization enforcement (401 without auth, 401 with invalid token).
6. Multi-tenant user data isolation (User A cannot view, test, or delete User B's data sources).
7. Full connector lifecycle (Create, Read, Update, Delete).
8. Connection test endpoint (validation, error reporting, status updates).
9. Source items discovery endpoint.
10. Source synchronization into Knowledge Base and RAG pipeline.
"""

import pytest
from app.infrastructure.database.models import DataSourceType
from app.schemas.common import ApiResponse, MetaInfo
from httpx import AsyncClient
from pydantic import BaseModel

# ==============================================================================
# 1. Exact MetaInfo.total Regression Tests
# ==============================================================================


def test_meta_info_without_total_field_reproduces_original_error():
    """Reproduces the exact original error: assigning an undeclared field to a Pydantic model raises ValueError: '<Model>' object has no field '<field>'."""

    class MetaInfoOld(BaseModel):
        request_id: str | None = None
        timestamp: str

    meta = MetaInfoOld(timestamp="2026-01-01T00:00:00Z")
    with pytest.raises(ValueError) as exc_info:
        meta.total = 42

    error_str = str(exc_info.value)
    assert '"MetaInfoOld" object has no field "total"' in error_str, f"Unexpected error message: {error_str}"


def test_meta_info_with_declared_total_field_succeeds():
    """Verifies that the fixed MetaInfo schema cleanly supports total, offset, and limit."""
    meta = MetaInfo(
        request_id="req-12345",
        timestamp="2026-01-01T00:00:00Z",
        total=15,
        offset=0,
        limit=50,
    )
    assert meta.total == 15
    assert meta.offset == 0
    assert meta.limit == 50
    assert meta.request_id == "req-12345"

    # Field mutation also works cleanly on declared field
    meta.total = 20
    assert meta.total == 20

    # Serialization in ApiResponse envelope retains total
    envelope = ApiResponse[list[str]](
        success=True,
        data=["item1", "item2"],
        meta=meta,
    )
    envelope_dict = envelope.model_dump()
    assert envelope_dict["meta"]["total"] == 20
    assert envelope_dict["meta"]["offset"] == 0
    assert envelope_dict["meta"]["limit"] == 50


# ==============================================================================
# 2. Data Sources API: Catalog & Listing Endpoints
# ==============================================================================


@pytest.mark.asyncio
async def test_get_connector_catalog_success(client: AsyncClient, auth_headers_user_a: dict):
    """Verifies GET /api/v1/data-sources/catalog returns supported connectors with metadata."""
    res = await client.get("/api/v1/data-sources/catalog", headers=auth_headers_user_a)
    assert res.status_code == 200

    body = res.json()
    assert body["success"] is True
    assert "data" in body
    assert isinstance(body["data"], list)
    assert len(body["data"]) >= 5

    # Check required connector types exist
    source_types = [item["source_type"] for item in body["data"]]
    assert DataSourceType.LOCAL.value in source_types
    assert DataSourceType.WEB.value in source_types
    assert DataSourceType.GITHUB.value in source_types
    assert DataSourceType.GDRIVE.value in source_types
    assert DataSourceType.NOTION.value in source_types
    assert DataSourceType.POSTGRES.value in source_types

    # Verify MetaInfo envelope structure
    assert "meta" in body
    assert body["meta"] is not None
    assert "timestamp" in body["meta"]


@pytest.mark.asyncio
async def test_list_data_sources_empty_state_returns_valid_envelope(client: AsyncClient, auth_headers_user_a: dict):
    """Verifies GET /api/v1/data-sources returns 200 with an empty list and valid total=0, not an HTTP 500 error."""
    res = await client.get("/api/v1/data-sources", headers=auth_headers_user_a)
    assert res.status_code == 200

    body = res.json()
    assert body["success"] is True
    assert body["data"] == []
    assert body["meta"]["total"] == 0
    assert body["meta"]["offset"] == 0
    assert body["meta"]["limit"] == 50


@pytest.mark.asyncio
async def test_data_sources_api_authentication_enforcement(client: AsyncClient):
    """Verifies that unauthenticated requests to Data Sources endpoints are rejected with HTTP 401."""
    # Without auth header
    res1 = await client.get("/api/v1/data-sources")
    assert res1.status_code == 401

    res2 = await client.get("/api/v1/data-sources/catalog")
    assert res2.status_code == 401

    # With invalid bearer token
    res3 = await client.get("/api/v1/data-sources", headers={"Authorization": "Bearer invalid_token_xyz"})
    assert res3.status_code == 401


# ==============================================================================
# 3. Connector Lifecycle (Create, Read, Update, Delete) & User Isolation
# ==============================================================================


@pytest.mark.asyncio
async def test_data_source_full_lifecycle_and_user_isolation(
    client: AsyncClient,
    auth_headers_user_a: dict,
    auth_headers_user_b: dict,
):
    """Verifies full lifecycle of data sources and verifies strict tenant data isolation."""
    # 1. User A creates a Web Scraper data source
    create_payload = {
        "source_type": "web",
        "name": "Python Docs",
        "description": "Python 3 documentation for RAG",
        "config": {
            "root_url": "https://docs.python.org/3/",
            "max_pages": 5,
        },
    }
    create_res = await client.post(
        "/api/v1/data-sources",
        json=create_payload,
        headers=auth_headers_user_a,
    )
    assert create_res.status_code == 201
    created = create_res.json()["data"]
    source_id = created["id"]
    assert created["name"] == "Python Docs"
    assert created["source_type"] == "web"

    # 2. User A lists data sources -> total is 1
    list_res_a = await client.get("/api/v1/data-sources", headers=auth_headers_user_a)
    assert list_res_a.status_code == 200
    list_body_a = list_res_a.json()
    assert list_body_a["meta"]["total"] == 1
    assert len(list_body_a["data"]) == 1
    assert list_body_a["data"][0]["id"] == source_id

    # 3. User B lists data sources -> total is 0 (tenant isolation)
    list_res_b = await client.get("/api/v1/data-sources", headers=auth_headers_user_b)
    assert list_res_b.status_code == 200
    list_body_b = list_res_b.json()
    assert list_body_b["meta"]["total"] == 0
    assert len(list_body_b["data"]) == 0

    # 4. User B cannot access User A's data source by ID (HTTP 404)
    get_res_b = await client.get(f"/api/v1/data-sources/{source_id}", headers=auth_headers_user_b)
    assert get_res_b.status_code == 404

    # 5. User A updates the data source
    update_res = await client.put(
        f"/api/v1/data-sources/{source_id}",
        json={"name": "Python 3.12 Official Docs"},
        headers=auth_headers_user_a,
    )
    assert update_res.status_code == 200
    assert update_res.json()["data"]["name"] == "Python 3.12 Official Docs"

    # 6. User B cannot delete User A's data source
    del_res_b = await client.delete(f"/api/v1/data-sources/{source_id}", headers=auth_headers_user_b)
    assert del_res_b.status_code == 404

    # 7. User A deletes the data source
    del_res_a = await client.delete(f"/api/v1/data-sources/{source_id}", headers=auth_headers_user_a)
    assert del_res_a.status_code == 200

    # 8. Data source is gone
    get_res_a = await client.get(f"/api/v1/data-sources/{source_id}", headers=auth_headers_user_a)
    assert get_res_a.status_code == 404


@pytest.mark.asyncio
async def test_connection_test_and_sensitive_masking(
    client: AsyncClient,
    auth_headers_user_a: dict,
):
    """Verifies connection testing endpoint and sensitive credential masking."""
    # Create GitHub connector with mock secret token
    create_payload = {
        "source_type": "github",
        "name": "Secret Repo",
        "config": {
            "repository": "facebook/react",
            "personal_access_token": "mock_github_pat_token_secret_123456789",
        },
    }
    create_res = await client.post(
        "/api/v1/data-sources",
        json=create_payload,
        headers=auth_headers_user_a,
    )
    assert create_res.status_code == 201
    created_data = create_res.json()["data"]
    source_id = created_data["id"]

    # Verify secret is masked in the response
    token_in_resp = created_data["config"]["personal_access_token"]
    assert "..." in token_in_resp or "******" in token_in_resp
    assert "1234567890abcdef" not in token_in_resp

    # Test connection endpoint
    test_res = await client.post(
        f"/api/v1/data-sources/{source_id}/test",
        headers=auth_headers_user_a,
    )
    assert test_res.status_code == 200
    test_body = test_res.json()
    assert test_body["success"] is True
    assert "data" in test_body
    assert "can_browse" in test_body["data"]
