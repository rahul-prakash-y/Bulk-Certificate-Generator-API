"""
Tests for Certificate retrieval endpoint GET /certificates/{recipient_id}.
"""

import os
import pathlib
import uuid
import pytest

from bulk_cert_api.services.certificate_service import CertificateService


@pytest.mark.asyncio
async def test_download_valid_certificate(client):
    """GET /certificates/{recipient_id} downloads the generated PDF."""
    payload = {
        "event_name": "API Design Conference",
        "issued_date": "2025-10-11",
        "recipients": [
            {"name": "Diana Prince", "email": "diana@example.com"}
        ],
    }
    post_resp = await client.post("/jobs", json=payload)
    job_id = post_resp.json()["job_id"]

    status_resp = await client.get(f"/jobs/{job_id}")
    recipient_id = status_resp.json()["results"][0]["recipient_id"]

    get_cert_resp = await client.get(f"/certificates/{recipient_id}")
    assert get_cert_resp.status_code == 200
    assert get_cert_resp.headers["content-type"] == "application/pdf"
    assert get_cert_resp.content[:5] == b"%PDF-"
    assert len(get_cert_resp.content) > 1000


@pytest.mark.asyncio
async def test_download_nonexistent_recipient_returns_404(client):
    """GET /certificates/{unknown_uuid} returns 404."""
    fake_id = uuid.uuid4()
    response = await client.get(f"/certificates/{fake_id}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_download_failed_recipient_returns_404(client, monkeypatch):
    """Downloading a certificate for a recipient whose generation failed returns 404."""
    def mock_fail(self, data):
        raise OSError("Disk full")

    monkeypatch.setattr(CertificateService, "generate", mock_fail)

    payload = {
        "event_name": "Test Fail",
        "issued_date": "2025-10-11",
        "recipients": [{"name": "Fail Person", "email": "fail@example.com"}],
    }
    post_resp = await client.post("/jobs", json=payload)
    job_id = post_resp.json()["job_id"]

    status_resp = await client.get(f"/jobs/{job_id}")
    recipient_id = status_resp.json()["results"][0]["recipient_id"]

    get_resp = await client.get(f"/certificates/{recipient_id}")
    assert get_resp.status_code == 404
    assert "not available" in get_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_download_missing_file_from_disk_returns_404(client, test_env):
    """If the certificate PDF was deleted from disk, return 404 cleanly."""
    payload = {
        "event_name": "File Deletion Test",
        "issued_date": "2025-10-11",
        "recipients": [{"name": "Ghost User", "email": "ghost@example.com"}],
    }
    post_resp = await client.post("/jobs", json=payload)
    job_id = post_resp.json()["job_id"]

    status_resp = await client.get(f"/jobs/{job_id}")
    recipient_id = status_resp.json()["results"][0]["recipient_id"]

    # Delete the generated file from disk to simulate missing file
    cert_file = test_env["certs_dir"] / f"{recipient_id}.pdf"
    if cert_file.exists():
        os.remove(cert_file)

    get_resp = await client.get(f"/certificates/{recipient_id}")
    assert get_resp.status_code == 404
    assert "could not be found" in get_resp.json()["detail"].lower()
