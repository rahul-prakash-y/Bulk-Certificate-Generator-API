"""
Job orchestration service.

Creates a Job + Recipient rows, then iterates through each recipient
calling the CertificateService.  Each recipient is wrapped in its own
try/except so that one failure does not block the rest.

Design decision (documented in README):
    Processing is synchronous within the request.  The service layer is
    decoupled from FastAPI so it can be moved to BackgroundTasks or Celery
    with zero schema changes.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from bulk_cert_api.config import settings
from bulk_cert_api.models.job import Job
from bulk_cert_api.models.recipient import Recipient
from bulk_cert_api.schemas.job import JobStatus, RecipientStatus
from bulk_cert_api.services.certificate_service import CertificateData, CertificateService

logger = logging.getLogger(__name__)


class JobService:
    """Orchestrates bulk certificate generation jobs."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._cert_service = CertificateService(output_dir=settings.certificates_dir)

    async def create_and_process_job(
        self,
        event_name: str,
        issued_date: date,
        recipients: list[dict[str, str]],
    ) -> Job:
        """
        Create a new generation job and process all recipients.

        Parameters
        ----------
        event_name : str
            Name of the event / course.
        issued_date : date
            Certificate issue date.
        recipients : list[dict]
            Each dict must have ``name`` and ``email`` keys.

        Returns
        -------
        Job
            The fully processed Job with recipients eagerly loaded.
        """
        # 1. Create Job + Recipient rows
        job = Job(
            event_name=event_name,
            issued_date=issued_date.isoformat(),
            status=JobStatus.PROCESSING,
            total=len(recipients),
        )

        for r in recipients:
            recipient = Recipient(
                id=str(uuid.uuid4()),
                name=r["name"],
                email=r["email"],
                status=RecipientStatus.PENDING,
            )
            job.recipients.append(recipient)

        self._db.add(job)
        await self._db.commit()
        await self._db.refresh(job)

        logger.info(
            "Job %s created: %d recipients for '%s'",
            job.id,
            job.total,
            job.event_name,
        )

        # 2. Process each recipient independently
        succeeded = 0
        failed = 0

        for recipient in job.recipients:
            try:
                cert_data = CertificateData(
                    recipient_name=recipient.name,
                    recipient_email=recipient.email,
                    event_name=job.event_name,
                    issued_date=issued_date,
                    recipient_id=uuid.UUID(recipient.id),
                )
                filepath = self._cert_service.generate(cert_data)

                recipient.status = RecipientStatus.SUCCESS
                recipient.certificate_path = str(filepath)
                succeeded += 1

            except Exception as exc:
                # Log full error internally; store safe message on recipient
                logger.error(
                    "Certificate generation failed for recipient %s (%s): %s",
                    recipient.id,
                    recipient.name,
                    exc,
                )
                recipient.status = RecipientStatus.FAILED
                recipient.error = _safe_error_message(exc)
                failed += 1

        # 3. Update job aggregate counts and final status
        job.succeeded = succeeded
        job.failed = failed
        job.status = (
            JobStatus.COMPLETED if failed == 0
            else JobStatus.FAILED if succeeded == 0
            else JobStatus.COMPLETED  # partial success is still "completed"
        )

        await self._db.commit()
        await self._db.refresh(job)

        logger.info(
            "Job %s finished: %d succeeded, %d failed → %s",
            job.id,
            succeeded,
            failed,
            job.status,
        )
        return job

    async def get_job(self, job_id: str) -> Job | None:
        """Retrieve a job by ID, with recipients eagerly loaded."""
        return await self._db.get(Job, job_id)

    async def get_recipient(self, recipient_id: str) -> Recipient | None:
        """Retrieve an individual recipient by ID."""
        return await self._db.get(Recipient, recipient_id)


def _safe_error_message(exc: Exception) -> str:
    """
    Convert an exception to a user-safe message.

    Never exposes filesystem paths, stack traces, or internal details.
    """
    if isinstance(exc, ValueError):
        return f"Validation error: {exc}"
    if isinstance(exc, OSError):
        return "Certificate file could not be generated."
    return "An unexpected error occurred during certificate generation."
