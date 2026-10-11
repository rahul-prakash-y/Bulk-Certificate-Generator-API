"""
Tests for Jobs API endpoints (Module 4 & Module 6).

Covers:
- Creating a bulk generation job (single and multiple recipients)
- Duplicate recipient names handling
- Polling job status via GET /jobs/{job_id}
- Partial failure isolation: individual failure does not block other recipients
- Downloading all certificates as a ZIP archive
- 404 handling for unknown job IDs
"""

import io
import uuid
import zipfile
import pytest

from bulk_cert_api.services.certificate_service import CertificateService


@pytest.mark.asyncio
async def test_create_single_recipient_job(client):
    """POST /jobs successfully creates and processes a single-recipient job."""
    payload = {
        "event_name": "FastAPI Masterclass",
        "issued_date": "2025-10-11",
        "recipients": [
            {"name": "Alice Smith", "email": "alice@example.com"}
        ],
    }
    response = await client.post("/jobs", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "completed"
    assert data["total"] == 1
    assert data["succeeded"] == 1
    assert data["failed"] == 0


@pytest.mark.asyncio
async def test_create_bulk_recipients_job(client):
    """POST /jobs successfully creates and processes a batch of multiple recipients."""
    payload = {
        "event_name": "Cloud Architecture Summit 2025",
        "issued_date": "2025-10-15",
        "recipients": [
            {"name": f"Attendee {i}", "email": f"attendee{i}@example.com"}
            for i in range(5)
        ],
    }
    response = await client.post("/jobs", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["total"] == 5
    assert data["succeeded"] == 5
    assert data["failed"] == 0
    assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_duplicate_names_in_single_batch(client):
    """Duplicate recipient names within the same job should both succeed with distinct certificates."""
    payload = {
        "event_name": "Python Workshop",
        "issued_date": "2025-10-11",
        "recipients": [
            {"name": "Same Name", "email": "attendee1@example.com"},
            {"name": "Same Name", "email": "attendee2@example.com"},
        ],
    }
    response = await client.post("/jobs", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["total"] == 2
    assert data["succeeded"] == 2

    job_id = data["job_id"]
    status_resp = await client.get(f"/jobs/{job_id}")
    assert status_resp.status_code == 200
    results = status_resp.json()["results"]
    assert len(results) == 2
    # Ensure distinct recipient IDs and certificate URLs
    assert results[0]["recipient_id"] != results[1]["recipient_id"]
    assert results[0]["certificate_url"] != results[1]["certificate_url"]


@pytest.mark.asyncio
async def test_get_job_status_details(client):
    """GET /jobs/{job_id} returns complete progress and recipient results."""
    payload = {
        "event_name": "Web Security Bootcamp",
        "issued_date": "2025-11-01",
        "recipients": [
            {"name": "Bob Jones", "email": "bob@example.com"},
            {"name": "Carol Danvers", "email": "carol@example.com"},
        ],
    }
    post_resp = await client.post("/jobs", json=payload)
    job_id = post_resp.json()["job_id"]

    get_resp = await client.get(f"/jobs/{job_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["job_id"] == job_id
    assert data["status"] == "completed"
    assert data["total"] == 2
    assert data["succeeded"] == 2
    assert data["failed"] == 0
    assert len(data["results"]) == 2

    for r in data["results"]:
        assert r["status"] == "success"
        assert r["certificate_url"].startswith("/certificates/")
        assert r["error"] is None


@pytest.mark.asyncio
async def test_get_nonexistent_job_returns_404(client):
    """GET /jobs/{random_uuid} returns 404 Not Found."""
    fake_id = uuid.uuid4()
    response = await client.get(f"/jobs/{fake_id}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_partial_failure_isolation(client, monkeypatch):
    """
    Failure while generating one certificate must not block other valid certificates.
    Job status reflects both successful and failed recipients.
    """
    orig_generate = CertificateService.generate

    def mock_generate(self, data):
        # Simulate an internal generation failure for a specific recipient
        if data.recipient_name == "Faulty User":
            raise OSError("Simulated PDF generation I/O failure")
        return orig_generate(self, data)

    monkeypatch.setattr(CertificateService, "generate", mock_generate)

    payload = {
        "event_name": "Fault Tolerance Demo",
        "issued_date": "2025-10-11",
        "recipients": [
            {"name": "Valid User 1", "email": "valid1@example.com"},
            {"name": "Faulty User", "email": "faulty@example.com"},
            {"name": "Valid User 2", "email": "valid2@example.com"},
        ],
    }

    response = await client.post("/jobs", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["total"] == 3
    assert data["succeeded"] == 2
    assert data["failed"] == 1
    assert data["status"] == "completed"

    # Verify per-recipient results on GET /jobs/{id}
    job_id = data["job_id"]
    status_resp = await client.get(f"/jobs/{job_id}")
    results = status_resp.json()["results"]

    faulty = next(r for r in results if r["name"] == "Faulty User")
    assert faulty["status"] == "failed"
    assert faulty["certificate_url"] is None
    assert "could not be generated" in faulty["error"].lower()

    valid1 = next(r for r in results if r["name"] == "Valid User 1")
    assert valid1["status"] == "success"
    assert valid1["certificate_url"] is not None


@pytest.mark.asyncio
async def test_all_recipients_failed_job_status(client, monkeypatch):
    """When all recipients fail, the job status is 'failed'."""
    def mock_generate_all_fail(self, data):
        raise OSError("Global disk failure")

    monkeypatch.setattr(CertificateService, "generate", mock_generate_all_fail)

    payload = {
        "event_name": "Failure Job",
        "issued_date": "2025-10-11",
        "recipients": [
            {"name": "User 1", "email": "u1@example.com"},
            {"name": "User 2", "email": "u2@example.com"},
        ],
    }

    response = await client.post("/jobs", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["total"] == 2
    assert data["succeeded"] == 0
    assert data["failed"] == 2
    assert data["status"] == "failed"


@pytest.mark.asyncio
async def test_download_job_archive_zip(client):
    """GET /jobs/{job_id}/archive packages generated certificates into a valid ZIP."""
    payload = {
        "event_name": "Packaging Workshop",
        "issued_date": "2025-10-11",
        "recipients": [
            {"name": "Alice Smith", "email": "alice@example.com"},
            {"name": "Bob Jones", "email": "bob@example.com"},
        ],
    }
    post_resp = await client.post("/jobs", json=payload)
    job_id = post_resp.json()["job_id"]

    zip_resp = await client.get(f"/jobs/{job_id}/archive")
    assert zip_resp.status_code == 200
    assert zip_resp.headers["content-type"] == "application/zip"
    assert f'filename="certificates-{job_id}.zip"' in zip_resp.headers["content-disposition"]

    # Verify zip content
    zip_bytes = io.BytesIO(zip_resp.content)
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        file_list = zf.namelist()
        assert len(file_list) == 2
        for f in file_list:
            assert f.endswith(".pdf")
            file_data = zf.read(f)
            assert file_data[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_download_archive_nonexistent_job_returns_404(client):
    """GET /jobs/{random_uuid}/archive returns 404."""
    fake_id = uuid.uuid4()
    response = await client.get(f"/jobs/{fake_id}/archive")
    assert response.status_code == 404
