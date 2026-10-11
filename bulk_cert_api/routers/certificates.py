"""
Certificate download routes.

Endpoints:
- GET /certificates/{recipient_id}: Download an individual certificate PDF
"""

from __future__ import annotations

import pathlib
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from bulk_cert_api.database import get_db
from bulk_cert_api.schemas.job import RecipientStatus
from bulk_cert_api.services.job_service import JobService

router = APIRouter(prefix="/certificates", tags=["certificates"])


def _sanitize_name(name: str) -> str:
    """Sanitize name to prevent path traversal or invalid characters in filenames."""
    cleaned = re.sub(r"[^\w\s-]", "_", name)
    cleaned = re.sub(r"[-\s]+", "_", cleaned).strip("._ ")
    return cleaned or "certificate"


@router.get(
    "/{recipient_id}",
    summary="Download certificate PDF",
    description="Downloads the generated certificate PDF for a given recipient.",
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "The generated PDF certificate file.",
        },
        404: {"description": "Recipient not found or certificate not generated."},
    },
)
async def download_certificate(
    recipient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    job_service = JobService(db)
    recipient = await job_service.get_recipient(str(recipient_id))

    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipient {recipient_id} not found.",
        )

    if recipient.status != RecipientStatus.SUCCESS or not recipient.certificate_path:
        reason = recipient.error or "Generation pending or failed"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate not available for recipient {recipient_id}: {reason}",
        )

    filepath = pathlib.Path(recipient.certificate_path)
    if not filepath.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate file could not be found on storage.",
        )

    safe_name = _sanitize_name(recipient.name)
    filename = f"{safe_name}-certificate.pdf"

    return FileResponse(
        path=str(filepath),
        media_type="application/pdf",
        filename=filename,
    )
