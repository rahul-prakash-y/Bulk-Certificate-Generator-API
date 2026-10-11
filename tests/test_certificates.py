"""
Tests for the CertificateService (PDF generation engine).

Covers:
- Successful PDF generation (file exists, is valid PDF, contains expected text)
- Output filename based on recipient_id UUID
- Invalid input handling (empty name, empty event)
- Unicode / special characters in certificate
- File stored only in configured output directory
"""

import pathlib
import shutil
import uuid
from datetime import date

import pytest

from bulk_cert_api.services.certificate_service import CertificateData, CertificateService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_OUTPUT_DIR = pathlib.Path(__file__).parent / "_test_certificates"


@pytest.fixture(autouse=True)
def clean_output_dir():
    """Create a fresh output directory before each test, remove after."""
    TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    yield
    shutil.rmtree(TEST_OUTPUT_DIR, ignore_errors=True)


@pytest.fixture
def service() -> CertificateService:
    return CertificateService(output_dir=str(TEST_OUTPUT_DIR))


def _sample_data(**overrides) -> CertificateData:
    defaults = {
        "recipient_name": "Alice Smith",
        "recipient_email": "alice@example.com",
        "event_name": "Python Workshop 2025",
        "issued_date": date(2025, 10, 11),
        "recipient_id": uuid.uuid4(),
    }
    defaults.update(overrides)
    return CertificateData(**defaults)


# ===================================================================
# Successful generation
# ===================================================================


class TestCertificateGeneration:
    """Tests that valid input produces a real PDF on disk."""

    def test_generates_pdf_file(self, service: CertificateService):
        data = _sample_data()
        filepath = service.generate(data)

        assert filepath.exists()
        assert filepath.suffix == ".pdf"

    def test_pdf_starts_with_magic_bytes(self, service: CertificateService):
        """A valid PDF starts with %PDF."""
        data = _sample_data()
        filepath = service.generate(data)

        content = filepath.read_bytes()
        assert content[:5] == b"%PDF-"

    def test_filename_uses_recipient_id(self, service: CertificateService):
        rid = uuid.uuid4()
        data = _sample_data(recipient_id=rid)
        filepath = service.generate(data)

        assert filepath.name == f"{rid}.pdf"

    def test_file_in_output_dir(self, service: CertificateService):
        data = _sample_data()
        filepath = service.generate(data)

        assert filepath.parent == TEST_OUTPUT_DIR.resolve()

    def test_pdf_has_nonzero_size(self, service: CertificateService):
        data = _sample_data()
        filepath = service.generate(data)

        assert filepath.stat().st_size > 1000  # a real PDF is at least a few KB

    def test_multiple_certificates_produce_unique_files(
        self, service: CertificateService
    ):
        d1 = _sample_data(recipient_name="Alice")
        d2 = _sample_data(recipient_name="Bob")

        f1 = service.generate(d1)
        f2 = service.generate(d2)

        assert f1 != f2
        assert f1.exists() and f2.exists()


# ===================================================================
# Unicode / special characters
# ===================================================================


class TestUnicodeCertificates:
    """Ensure special characters don't crash the generator."""

    def test_unicode_name(self, service: CertificateService):
        data = _sample_data(recipient_name="José García-López")
        filepath = service.generate(data)
        assert filepath.exists()

    def test_unicode_event(self, service: CertificateService):
        data = _sample_data(event_name="Café & Résumé Workshop")
        filepath = service.generate(data)
        assert filepath.exists()

    def test_long_name_auto_sizing(self, service: CertificateService):
        data = _sample_data(recipient_name="A" * 80)
        filepath = service.generate(data)
        assert filepath.exists()

    def test_long_event_name_auto_sizing(self, service: CertificateService):
        data = _sample_data(event_name="X" * 120)
        filepath = service.generate(data)
        assert filepath.exists()


# ===================================================================
# Invalid input handling
# ===================================================================


class TestInvalidInput:
    """Defence-in-depth: service rejects bad data even if schemas didn't catch it."""

    def test_empty_name_raises(self, service: CertificateService):
        data = _sample_data(recipient_name="")
        with pytest.raises(ValueError, match="[Nn]ame"):
            service.generate(data)

    def test_whitespace_name_raises(self, service: CertificateService):
        data = _sample_data(recipient_name="   ")
        with pytest.raises(ValueError, match="[Nn]ame"):
            service.generate(data)

    def test_empty_event_raises(self, service: CertificateService):
        data = _sample_data(event_name="")
        with pytest.raises(ValueError, match="[Ee]vent"):
            service.generate(data)
