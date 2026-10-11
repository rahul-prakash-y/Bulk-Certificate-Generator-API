"""
Tests for health check and general API availability.
"""

import pytest


@pytest.mark.asyncio
async def test_health_check_endpoint(client):
    """GET /health returns 200 with status ok."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_openapi_docs_endpoint(client):
    """GET /docs and /openapi.json are accessible."""
    docs_resp = await client.get("/docs")
    assert docs_resp.status_code == 200

    openapi_resp = await client.get("/openapi.json")
    assert openapi_resp.status_code == 200
    schema = openapi_resp.json()
    assert "paths" in schema
    assert "/health" in schema["paths"]
    assert "/jobs" in schema["paths"]
    assert "/certificates/{recipient_id}" in schema["paths"]
