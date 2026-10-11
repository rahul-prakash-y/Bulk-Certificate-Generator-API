"""
End-to-end verification test using realistic sample data.

Verifies:
- Submitting a job with realistic names and event metadata.
- Retrieving the generated certificate PDF and actually parsing it with pypdf.
- Verifying page count, metadata, and extracted text.
- Downloading the bulk ZIP archive and verifying every member can be opened and parsed.
"""

import io
import zipfile
import pytest
from pypdf import PdfReader


@pytest.mark.asyncio
async def test_realistic_sample_data_and_verify_files_openable(client):
    """
    Submits realistic sample data, downloads the generated PDF certificates,
    and asserts that they can be opened and read as valid PDFs.
    """
    payload = {
        "event_name": "Advanced Python & Distributed Systems Certification",
        "issued_date": "2025-10-15",
        "recipients": [
            {"name": "Dr. Alexander Wright", "email": "a.wright@university.edu"},
            {"name": "Priya Patel", "email": "priya.patel@techcorp.io"},
            {"name": "Carlos Gomez-Santos", "email": "carlos.gomez@globalnet.org"},
        ],
    }

    # 1. Submit bulk job
    create_resp = await client.post("/jobs", json=payload)
    assert create_resp.status_code == 202
    job_info = create_resp.json()
    job_id = job_info["job_id"]
    assert job_info["succeeded"] == 3
    assert job_info["failed"] == 0

    # 2. Check job status
    status_resp = await client.get(f"/jobs/{job_id}")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert len(status_data["results"]) == 3

    # 3. Download and verify each individual certificate PDF can actually be opened
    for r in status_data["results"]:
        recipient_id = r["recipient_id"]
        recipient_name = r["name"]

        cert_resp = await client.get(f"/certificates/{recipient_id}")
        assert cert_resp.status_code == 200
        assert cert_resp.headers["content-type"] == "application/pdf"

        # Parse with pypdf to verify file integrity
        pdf_stream = io.BytesIO(cert_resp.content)
        reader = PdfReader(pdf_stream)

        # Must have exactly 1 page
        assert len(reader.pages) == 1
        page = reader.pages[0]

        # Extract text and verify recipient and event information
        text = page.extract_text()
        assert "CERTIFICATE" in text
        assert recipient_name in text
        assert "Advanced Python" in text

    # 4. Download bulk ZIP archive and verify every PDF inside can be opened
    archive_resp = await client.get(f"/jobs/{job_id}/archive")
    assert archive_resp.status_code == 200
    assert archive_resp.headers["content-type"] == "application/zip"

    zip_stream = io.BytesIO(archive_resp.content)
    with zipfile.ZipFile(zip_stream, "r") as zf:
        members = zf.namelist()
        assert len(members) == 3

        for member_name in members:
            assert member_name.endswith(".pdf")
            pdf_bytes = zf.read(member_name)
            # Verify each zipped file opens in pypdf
            member_reader = PdfReader(io.BytesIO(pdf_bytes))
            assert len(member_reader.pages) == 1
            member_text = member_reader.pages[0].extract_text()
            assert "CERTIFICATE" in member_text
