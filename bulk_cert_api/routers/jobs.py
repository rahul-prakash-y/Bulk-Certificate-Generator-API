"""
Job management routes.

Endpoints:
- POST /jobs: Submit bulk certificate generation job
- GET /jobs/{job_id}: Poll job status and per-recipient results
- GET /jobs/{job_id}/archive: Download all generated certificates as a ZIP archive
"""

from __future__ import annotations

import io
import pathlib
import re
import uuid
import zipfile

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from bulk_cert_api.database import get_db
from bulk_cert_api.schemas.job import (
    JobCreateRequest,
    JobCreateResponse,
    JobStatusResponse,
    RecipientResponse,
    RecipientStatus,
)
from bulk_cert_api.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _sanitize_name(name: str) -> str:
    """Sanitize name to prevent path traversal or invalid characters in filenames."""
    cleaned = re.sub(r"[^\w\s-]", "_", name)
    cleaned = re.sub(r"[-\s]+", "_", cleaned).strip("._ ")
    return cleaned or "certificate"


@router.post(
    "",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit bulk certificate generation job",
    description=(
        "Accepts event details and a list of recipients. Generates certificates "
        "and tracks job progress. Returns HTTP 202 with job metadata."
    ),
)
async def create_job(
    payload: JobCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> JobCreateResponse:
    job_service = JobService(db)
    recipients_data = [
        {"name": r.name, "email": str(r.email)} for r in payload.recipients
    ]
    job = await job_service.create_and_process_job(
        event_name=payload.event_name,
        issued_date=payload.issued_date,
        recipients=recipients_data,
    )

    return JobCreateResponse(
        job_id=uuid.UUID(job.id),
        status=job.status,
        total=job.total,
        succeeded=job.succeeded,
        failed=job.failed,
        created_at=job.created_at,
    )


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status and recipient results",
    description="Returns the current status, aggregate counts, and individual recipient outcomes.",
)
async def get_job_status(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> JobStatusResponse:
    job_service = JobService(db)
    job = await job_service.get_job(str(job_id))

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found.",
        )

    results = [
        RecipientResponse(
            recipient_id=uuid.UUID(r.id),
            name=r.name,
            email=r.email,
            status=r.status,
            error=r.error,
            certificate_url=(
                f"/certificates/{r.id}"
                if r.status == RecipientStatus.SUCCESS
                else None
            ),
        )
        for r in job.recipients
    ]

    return JobStatusResponse(
        job_id=uuid.UUID(job.id),
        status=job.status,
        total=job.total,
        succeeded=job.succeeded,
        failed=job.failed,
        created_at=job.created_at,
        updated_at=job.updated_at,
        results=results,
    )


@router.get(
    "/{job_id}/archive",
    summary="Download all certificates as a ZIP archive",
    description="Packages all successfully generated certificates for this job into a ZIP archive.",
)
async def download_job_archive(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    job_service = JobService(db)
    job = await job_service.get_job(str(job_id))

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found.",
        )

    valid_recipients = [
        r
        for r in job.recipients
        if r.status == RecipientStatus.SUCCESS
        and r.certificate_path
        and pathlib.Path(r.certificate_path).exists()
    ]

    if not valid_recipients:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No generated certificates available for job {job_id}.",
        )

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        used_names: set[str] = set()
        for r in valid_recipients:
            # Sanitize name to prevent path traversal or invalid characters
            safe_name = _sanitize_name(r.name)
            # Ensure unique filename to prevent collisions within zip
            arcname = f"{safe_name}_{r.id[:8]}.pdf"
            if arcname in used_names:
                arcname = f"{safe_name}_{r.id}.pdf"
            used_names.add(arcname)

            zf.write(r.certificate_path, arcname=arcname)

    zip_buffer.seek(0)
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="certificates-{job.id}.zip"'
        },
    )
