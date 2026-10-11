"""
ORM model for a certificate generation job.

A Job is the top-level record created by ``POST /jobs``.  It tracks overall
status and aggregate counts while individual recipient results are stored
in the ``Recipient`` model.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bulk_cert_api.database import Base
from bulk_cert_api.schemas.job import JobStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    event_name: Mapped[str] = mapped_column(String(200), nullable=False)
    issued_date: Mapped[str] = mapped_column(String(10), nullable=False)  # ISO date
    status: Mapped[str] = mapped_column(
        Enum(JobStatus), nullable=False, default=JobStatus.PENDING
    )
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    succeeded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationship
    recipients: Mapped[list["Recipient"]] = relationship(
        "Recipient", back_populates="job", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Job id={self.id} status={self.status}>"
