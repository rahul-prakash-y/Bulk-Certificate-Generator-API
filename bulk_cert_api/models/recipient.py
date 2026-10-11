"""
ORM model for an individual certificate recipient within a job.

Each Recipient row corresponds to one certificate generation attempt.
On success the ``certificate_path`` is populated with the on-disk path;
on failure the ``error`` column records a safe, user-facing message.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bulk_cert_api.database import Base
from bulk_cert_api.schemas.job import RecipientStatus


class Recipient(Base):
    __tablename__ = "recipients"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(RecipientStatus), nullable=False, default=RecipientStatus.PENDING
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    certificate_path: Mapped[str | None] = mapped_column(
        String(500), nullable=True, default=None
    )

    # Relationship
    job: Mapped["Job"] = relationship("Job", back_populates="recipients")

    def __repr__(self) -> str:
        return f"<Recipient id={self.id} name={self.name} status={self.status}>"
