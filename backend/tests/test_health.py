"""Health and system endpoint tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "self-healing-rag-agent"
    assert "version" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_liveness_endpoint(client: AsyncClient):
    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert data["service"] == "self-healing-rag-agent"
    assert "uptime_seconds" in data
    assert isinstance(data["uptime_seconds"], int | float)


@pytest.mark.asyncio
async def test_readiness_endpoint_structure(client: AsyncClient):
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "ready" in data
    assert "dependencies" in data
    assert "database" in data["dependencies"]
    assert "redis" in data["dependencies"]


@pytest.mark.asyncio
async def test_system_info_endpoint(client: AsyncClient):
    response = await client.get("/api/v1/system/info")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "self-healing-rag-agent"
    assert "version" in data
    assert "python_version" in data
    assert "features" in data
    assert isinstance(data["features"], dict)
