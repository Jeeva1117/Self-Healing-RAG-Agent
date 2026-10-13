"""Centralized error handling tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_not_found_structured_error(client: AsyncClient):
    response = await client.get("/api/v1/nonexistent-endpoint-12345")
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert "error" in data
    assert data["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert "message" in data["error"]
