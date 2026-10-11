"""
Tests for Pydantic request/response schemas and input validation.

Covers:
- Valid input acceptance
- Missing required fields
- Invalid types (wrong date format, non-string name, etc.)
- Empty / whitespace-only strings
- Empty recipients list
- Email validation
- Boundary conditions (max lengths)
"""

import pytest
from pydantic import ValidationError

from bulk_cert_api.schemas.job import (
    MAX_EVENT_NAME_LENGTH,
    MAX_RECIPIENT_NAME_LENGTH,
    JobCreateRequest,
    RecipientRequest,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_payload(**overrides) -> dict:
    """Return a valid JobCreateRequest dict with optional overrides."""
    base = {
        "event_name": "Python Workshop 2025",
        "issued_date": "2025-10-11",
        "recipients": [
            {"name": "Alice Smith", "email": "alice@example.com"},
        ],
    }
    base.update(overrides)
    return base


def _valid_recipient(**overrides) -> dict:
    base = {"name": "Alice Smith", "email": "alice@example.com"}
    base.update(overrides)
    return base


# ===================================================================
# RecipientRequest tests
# ===================================================================


class TestRecipientRequest:
    """Unit tests for the RecipientRequest schema."""

    def test_valid_recipient(self):
        r = RecipientRequest(**_valid_recipient())
        assert r.name == "Alice Smith"
        assert r.email == "alice@example.com"

    def test_name_stripped(self):
        r = RecipientRequest(**_valid_recipient(name="  Bob Jones  "))
        assert r.name == "Bob Jones"

    def test_name_missing(self):
        with pytest.raises(ValidationError) as exc_info:
            RecipientRequest(email="a@b.com")
        assert "name" in str(exc_info.value).lower()

    def test_name_empty_string(self):
        with pytest.raises(ValidationError):
            RecipientRequest(**_valid_recipient(name=""))

    def test_name_whitespace_only(self):
        with pytest.raises(ValidationError):
            RecipientRequest(**_valid_recipient(name="   "))

    def test_name_too_long(self):
        with pytest.raises(ValidationError):
            RecipientRequest(**_valid_recipient(name="A" * (MAX_RECIPIENT_NAME_LENGTH + 1)))

    def test_name_at_max_length(self):
        r = RecipientRequest(**_valid_recipient(name="A" * MAX_RECIPIENT_NAME_LENGTH))
        assert len(r.name) == MAX_RECIPIENT_NAME_LENGTH

    def test_email_missing(self):
        with pytest.raises(ValidationError) as exc_info:
            RecipientRequest(name="Alice")
        assert "email" in str(exc_info.value).lower()

    def test_email_invalid_format(self):
        with pytest.raises(ValidationError):
            RecipientRequest(**_valid_recipient(email="not-an-email"))

    def test_email_missing_domain(self):
        with pytest.raises(ValidationError):
            RecipientRequest(**_valid_recipient(email="alice@"))

    def test_email_missing_local(self):
        with pytest.raises(ValidationError):
            RecipientRequest(**_valid_recipient(email="@example.com"))

    def test_email_empty(self):
        with pytest.raises(ValidationError):
            RecipientRequest(**_valid_recipient(email=""))

    def test_name_non_string_type(self):
        with pytest.raises(ValidationError):
            RecipientRequest(**_valid_recipient(name=12345))


# ===================================================================
# JobCreateRequest tests
# ===================================================================


class TestJobCreateRequest:
    """Unit tests for the JobCreateRequest schema."""

    # --- Valid input ---

    def test_valid_request(self):
        req = JobCreateRequest(**_valid_payload())
        assert req.event_name == "Python Workshop 2025"
        assert str(req.issued_date) == "2025-10-11"
        assert len(req.recipients) == 1

    def test_multiple_recipients(self):
        payload = _valid_payload(
            recipients=[
                {"name": "Alice", "email": "alice@example.com"},
                {"name": "Bob", "email": "bob@example.com"},
                {"name": "Charlie", "email": "charlie@example.com"},
            ]
        )
        req = JobCreateRequest(**payload)
        assert len(req.recipients) == 3

    # --- event_name ---

    def test_event_name_missing(self):
        p = _valid_payload()
        del p["event_name"]
        with pytest.raises(ValidationError) as exc_info:
            JobCreateRequest(**p)
        assert "event_name" in str(exc_info.value).lower()

    def test_event_name_empty(self):
        with pytest.raises(ValidationError):
            JobCreateRequest(**_valid_payload(event_name=""))

    def test_event_name_whitespace_only(self):
        with pytest.raises(ValidationError):
            JobCreateRequest(**_valid_payload(event_name="   "))

    def test_event_name_stripped(self):
        req = JobCreateRequest(**_valid_payload(event_name="  My Event  "))
        assert req.event_name == "My Event"

    def test_event_name_too_long(self):
        with pytest.raises(ValidationError):
            JobCreateRequest(
                **_valid_payload(event_name="E" * (MAX_EVENT_NAME_LENGTH + 1))
            )

    def test_event_name_at_max(self):
        req = JobCreateRequest(
            **_valid_payload(event_name="E" * MAX_EVENT_NAME_LENGTH)
        )
        assert len(req.event_name) == MAX_EVENT_NAME_LENGTH

    # --- issued_date ---

    def test_issued_date_missing(self):
        p = _valid_payload()
        del p["issued_date"]
        with pytest.raises(ValidationError):
            JobCreateRequest(**p)

    def test_issued_date_invalid_format(self):
        with pytest.raises(ValidationError):
            JobCreateRequest(**_valid_payload(issued_date="11-10-2025"))

    def test_issued_date_not_a_date(self):
        with pytest.raises(ValidationError):
            JobCreateRequest(**_valid_payload(issued_date="not-a-date"))

    def test_issued_date_valid_iso(self):
        req = JobCreateRequest(**_valid_payload(issued_date="2025-01-01"))
        assert str(req.issued_date) == "2025-01-01"

    # --- recipients list ---

    def test_recipients_missing(self):
        p = _valid_payload()
        del p["recipients"]
        with pytest.raises(ValidationError):
            JobCreateRequest(**p)

    def test_recipients_empty_list(self):
        with pytest.raises(ValidationError):
            JobCreateRequest(**_valid_payload(recipients=[]))

    def test_recipients_not_a_list(self):
        with pytest.raises(ValidationError):
            JobCreateRequest(**_valid_payload(recipients="not-a-list"))

    def test_recipients_contains_invalid_item(self):
        """One bad recipient should cause the whole request to fail."""
        with pytest.raises(ValidationError):
            JobCreateRequest(
                **_valid_payload(
                    recipients=[
                        {"name": "Alice", "email": "alice@example.com"},
                        {"name": "", "email": "bad"},
                    ]
                )
            )

    # --- Unicode / special characters ---

    def test_unicode_name(self):
        req = JobCreateRequest(
            **_valid_payload(
                recipients=[
                    {"name": "José García-López", "email": "jose@example.com"},
                ]
            )
        )
        assert req.recipients[0].name == "José García-López"

    def test_unicode_event_name(self):
        req = JobCreateRequest(
            **_valid_payload(event_name="Café & Résumé Workshop")
        )
        assert req.event_name == "Café & Résumé Workshop"
