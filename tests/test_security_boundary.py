"""
Tests covering security, boundary conditions, and invalid API requests.
"""

import io
import zipfile
import pytest


@pytest.mark.asyncio
async def test_path_traversal_in_recipient_name(client, test_env):
    """
    Attempting path traversal in recipient name must never write outside the
    configured certificate directory or corrupt archive structures.
    """
    payload = {
        "event_name": "Security Test Event",
        "issued_date": "2025-10-11",
        "recipients": [
            {"name": "../../../traversal_user", "email": "trav@example.com"},
            {"name": "C:\\Windows\\System32\\cmd", "email": "cmd@example.com"},
        ],
    }
    response = await client.post("/jobs", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["succeeded"] == 2

    # Check disk files: all files must reside strictly inside test_env["certs_dir"]
    certs_dir = test_env["certs_dir"]
    all_files = list(certs_dir.glob("*.pdf"))
    assert len(all_files) == 2
    for f in all_files:
        assert f.parent == certs_dir.resolve()

    # Check archive: all zip member names must be safe (no ../ or absolute paths)
    job_id = data["job_id"]
    zip_resp = await client.get(f"/jobs/{job_id}/archive")
    assert zip_resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as zf:
        for name in zf.namelist():
            assert not name.startswith("/")
            assert not name.startswith("\\")
            assert ".." not in name


@pytest.mark.asyncio
async def test_xss_and_injection_strings_in_name(client):
    """XSS strings and SQL injection payloads are handled safely as plain strings."""
    payload = {
        "event_name": "SQLi & XSS Event '<script>alert(1)</script>'",
        "issued_date": "2025-10-11",
        "recipients": [
            {
                "name": "<script>alert('xss')</script>' OR '1'='1' --",
                "email": "sqli@example.com",
            }
        ],
    }
    response = await client.post("/jobs", json=payload)
    assert response.status_code == 202
    assert response.json()["succeeded"] == 1


@pytest.mark.asyncio
async def test_empty_recipients_batch_returns_422(client):
    """Submitting an empty recipients list returns 422 Unprocessable Entity."""
    payload = {
        "event_name": "Empty Batch Event",
        "issued_date": "2025-10-11",
        "recipients": [],
    }
    response = await client.post("/jobs", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_invalid_uuid_param_returns_422(client):
    """Passing a non-UUID parameter to job or certificate endpoints returns 422."""
    resp1 = await client.get("/jobs/not-a-valid-uuid")
    assert resp1.status_code == 422

    resp2 = await client.get("/certificates/not-a-valid-uuid")
    assert resp2.status_code == 422


@pytest.mark.asyncio
async def test_missing_required_fields_return_422(client):
    """Missing top-level required fields return 422."""
    # Missing event_name
    resp = await client.post(
        "/jobs",
        json={"issued_date": "2025-10-11", "recipients": [{"name": "A", "email": "a@a.com"}]},
    )
    assert resp.status_code == 422

    # Missing issued_date
    resp = await client.post(
        "/jobs",
        json={"event_name": "Workshop", "recipients": [{"name": "A", "email": "a@a.com"}]},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_invalid_date_format_returns_422(client):
    """Invalid date string format returns 422."""
    payload = {
        "event_name": "Date Test",
        "issued_date": "11-10-2025",  # Not ISO YYYY-MM-DD
        "recipients": [{"name": "A", "email": "a@a.com"}],
    }
    response = await client.post("/jobs", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_batch_boundary_size(client):
    """Processing a large batch of 25 recipients in a single request."""
    recipients = [
        {"name": f"Batch Member {i}", "email": f"member{i}@example.com"}
        for i in range(25)
    ]
    payload = {
        "event_name": "Annual General Meeting 2025",
        "issued_date": "2025-10-11",
        "recipients": recipients,
    }
    response = await client.post("/jobs", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["total"] == 25
    assert data["succeeded"] == 25
    assert data["failed"] == 0


@pytest.mark.asyncio
async def test_batch_size_exceeding_max_limit_returns_422(client):
    """Submitting more than MAX_BATCH_SIZE (500) recipients returns 422."""
    recipients = [
        {"name": f"Member {i}", "email": f"m{i}@example.com"}
        for i in range(501)
    ]
    payload = {
        "event_name": "Over Limit Event",
        "issued_date": "2025-10-11",
        "recipients": recipients,
    }
    response = await client.post("/jobs", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_os_reserved_name_sanitization(client):
    """Names matching OS reserved keywords (CON, PRN, AUX, NUL) are safely sanitized."""
    payload = {
        "event_name": "Reserved Name Event",
        "issued_date": "2025-10-11",
        "recipients": [
            {"name": "CON", "email": "con@example.com"},
            {"name": "NUL", "email": "nul@example.com"},
        ],
    }
    response = await client.post("/jobs", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["succeeded"] == 2

    job_id = data["job_id"]
    status_resp = await client.get(f"/jobs/{job_id}")
    recipient_id = status_resp.json()["results"][0]["recipient_id"]

    # Verify download succeeds with safe filename
    dl_resp = await client.get(f"/certificates/{recipient_id}")
    assert dl_resp.status_code == 200
    assert "content-disposition" in dl_resp.headers


@pytest.mark.asyncio
async def test_unhandled_exception_masks_internal_details(client, monkeypatch):
    """Unhandled exceptions return a safe generic 500 response without stack traces."""
    from bulk_cert_api.services.job_service import JobService

    async def mock_crash(*args, **kwargs):
        raise RuntimeError("Secret DB credentials and internal server crash: /etc/secrets/key.pem")

    monkeypatch.setattr(JobService, "create_and_process_job", mock_crash)

    payload = {
        "event_name": "Crash Event",
        "issued_date": "2025-10-11",
        "recipients": [{"name": "Crash User", "email": "crash@example.com"}],
    }
    from bulk_cert_api.main import app
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as unhandled_client:
        response = await unhandled_client.post("/jobs", json=payload)

    assert response.status_code == 500
    data = response.json()
    assert data["detail"] == "An internal server error occurred. Please try again later."
    assert "Secret" not in str(data)
    assert "traceback" not in str(data).lower()
    assert "/etc/secrets" not in str(data)
