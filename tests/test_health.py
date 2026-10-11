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


@pytest.mark.asyncio
async def test_lifespan_startup_and_shutdown(tmp_path, monkeypatch):
    """Verify lifespan context creates certificate directory and initializes database."""
    from bulk_cert_api.config import settings
    from bulk_cert_api.main import create_app, lifespan

    test_certs = tmp_path / "lifespan_certs"
    monkeypatch.setattr(settings, "certificates_dir", str(test_certs))

    app_instance = create_app()
    async with lifespan(app_instance):
        assert test_certs.exists()
        assert test_certs.is_dir()
