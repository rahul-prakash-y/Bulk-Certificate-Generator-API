"""
Pydantic schemas for certificate generation requests and responses.

Validation rules (derived from the assignment specification):
- event_name:  required, non-empty after stripping, max 200 characters
- issued_date: required, valid date (ISO format)
- recipients:  required, non-empty list (at least 1 recipient)
- name:        required, non-empty after stripping, max 150 characters
- email:       required, valid email format

The assignment does not specify batch-size caps or additional fields.
Limits above are practical guardrails; they do not conflict with the spec.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Constants — configurable limits (not from spec, just sensible guardrails)
# ---------------------------------------------------------------------------

MAX_EVENT_NAME_LENGTH = 200
MAX_RECIPIENT_NAME_LENGTH = 150


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class JobStatus(str, Enum):
    """Lifecycle status of a generation job."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RecipientStatus(str, Enum):
    """Status of an individual recipient's certificate generation."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class RecipientRequest(BaseModel):
    """A single recipient within a certificate generation request."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=MAX_RECIPIENT_NAME_LENGTH,
        description="Full name of the certificate recipient.",
        examples=["Alice Smith"],
    )
    email: EmailStr = Field(
        ...,
        description="Email address of the recipient.",
        examples=["alice@example.com"],
    )

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        """Strip leading/trailing whitespace so that '  ' is caught by min_length."""
        if isinstance(v, str):
            return v.strip()
        return v


class JobCreateRequest(BaseModel):
    """Top-level request body for POST /jobs."""

    event_name: str = Field(
        ...,
        min_length=1,
        max_length=MAX_EVENT_NAME_LENGTH,
        description="Name of the event or course for which certificates are issued.",
        examples=["Python Workshop 2025"],
    )
    issued_date: date = Field(
        ...,
        description="Date the certificate is issued (ISO 8601 format: YYYY-MM-DD).",
        examples=["2025-10-11"],
    )
    recipients: list[RecipientRequest] = Field(
        ...,
        min_length=1,
        description="List of recipients. Must contain at least one entry.",
    )

    @field_validator("event_name", mode="before")
    @classmethod
    def strip_event_name(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class RecipientResponse(BaseModel):
    """Status of a single recipient within a job response."""

    recipient_id: uuid.UUID
    name: str
    email: str
    status: RecipientStatus
    error: Optional[str] = None
    certificate_url: Optional[str] = None


class JobCreateResponse(BaseModel):
    """Response returned when a job is created (POST /jobs → 202)."""

    job_id: uuid.UUID
    status: JobStatus
    total: int
    succeeded: int
    failed: int
    created_at: datetime


class JobStatusResponse(BaseModel):
    """Full job status including per-recipient details (GET /jobs/{id})."""

    job_id: uuid.UUID
    status: JobStatus
    total: int
    succeeded: int
    failed: int
    created_at: datetime
    updated_at: datetime
    results: list[RecipientResponse]
