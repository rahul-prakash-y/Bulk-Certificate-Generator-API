"""
Certificate PDF generation service.

Generates a single PDF certificate from validated recipient data using
ReportLab.  The template is a single predefined design — no template editor
or multiple designs are required (per assignment spec).

Design decisions:
- A4 landscape orientation for a natural certificate look.
- Gold/navy colour scheme with decorative border.
- Dynamic fields: recipient name, event name, issued date.
- Unique filenames based on UUID to prevent collisions and path traversal.
- Output stored in the configured ``CERTIFICATES_DIR``.
"""

from __future__ import annotations

import logging
import pathlib
import uuid
from dataclasses import dataclass
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm, mm
from reportlab.pdfgen.canvas import Canvas

logger = logging.getLogger(__name__)

# Page dimensions (A4 landscape)
PAGE_W, PAGE_H = landscape(A4)

# Colour palette
NAVY = colors.HexColor("#1B2A4A")
GOLD = colors.HexColor("#C9A84C")
DARK_GOLD = colors.HexColor("#8B6914")
LIGHT_BG = colors.HexColor("#FDFAF3")
TEXT_DARK = colors.HexColor("#1A1A1A")
TEXT_MUTED = colors.HexColor("#555555")


@dataclass(frozen=True)
class CertificateData:
    """Validated input data for a single certificate."""

    recipient_name: str
    recipient_email: str
    event_name: str
    issued_date: date
    recipient_id: uuid.UUID


class CertificateService:
    """Generates PDF certificates using a predefined template."""

    def __init__(self, output_dir: str) -> None:
        self._output_dir = pathlib.Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, data: CertificateData) -> pathlib.Path:
        """
        Generate a PDF certificate for a single recipient.

        Returns the absolute path to the generated PDF file.
        Raises ``ValueError`` for invalid data and ``OSError`` for I/O
        problems.
        """
        self._validate(data)

        filename = f"{data.recipient_id}.pdf"
        filepath = self._output_dir / filename

        logger.info("Generating certificate for recipient_id=%s", data.recipient_id)

        self._render_pdf(filepath, data)

        if not filepath.exists():
            raise OSError(f"Certificate file was not created: {filepath.name}")

        logger.info("Certificate generated successfully for recipient_id=%s", data.recipient_id)
        return filepath.resolve()

    # ------------------------------------------------------------------
    # Validation (defence-in-depth; schemas validate first)
    # ------------------------------------------------------------------

    @staticmethod
    def _validate(data: CertificateData) -> None:
        if not data.recipient_name or not data.recipient_name.strip():
            raise ValueError("Recipient name must not be empty.")
        if not data.event_name or not data.event_name.strip():
            raise ValueError("Event name must not be empty.")

    # ------------------------------------------------------------------
    # PDF rendering
    # ------------------------------------------------------------------

    def _render_pdf(self, filepath: pathlib.Path, data: CertificateData) -> None:
        """Build the certificate PDF on disk."""
        c = Canvas(str(filepath), pagesize=landscape(A4))
        c.setTitle(f"Certificate – {data.recipient_name}")
        c.setAuthor("Bulk Certificate Generator")

        self._draw_background(c)
        self._draw_border(c)
        self._draw_header(c)
        self._draw_recipient_name(c, data.recipient_name)
        self._draw_body(c, data.event_name, data.issued_date)
        self._draw_footer(c, data.recipient_id)

        c.save()

    # --- Background ---

    @staticmethod
    def _draw_background(c: Canvas) -> None:
        c.setFillColor(LIGHT_BG)
        c.rect(0, 0, PAGE_W, PAGE_H, fill=True, stroke=False)

    # --- Decorative border ---

    @staticmethod
    def _draw_border(c: Canvas) -> None:
        margin = 1.2 * cm
        inner_margin = 1.6 * cm

        # Outer border — navy
        c.setStrokeColor(NAVY)
        c.setLineWidth(3)
        c.rect(margin, margin, PAGE_W - 2 * margin, PAGE_H - 2 * margin)

        # Inner border — gold
        c.setStrokeColor(GOLD)
        c.setLineWidth(1.5)
        c.rect(
            inner_margin,
            inner_margin,
            PAGE_W - 2 * inner_margin,
            PAGE_H - 2 * inner_margin,
        )

        # Corner ornaments (small gold squares)
        ornament_size = 6 * mm
        for x, y in [
            (margin + 2 * mm, margin + 2 * mm),
            (PAGE_W - margin - ornament_size - 2 * mm, margin + 2 * mm),
            (margin + 2 * mm, PAGE_H - margin - ornament_size - 2 * mm),
            (
                PAGE_W - margin - ornament_size - 2 * mm,
                PAGE_H - margin - ornament_size - 2 * mm,
            ),
        ]:
            c.setFillColor(GOLD)
            c.rect(x, y, ornament_size, ornament_size, fill=True, stroke=False)

    # --- Header ---

    @staticmethod
    def _draw_header(c: Canvas) -> None:
        y = PAGE_H - 3.5 * cm

        # "CERTIFICATE" title
        c.setFont("Helvetica-Bold", 36)
        c.setFillColor(NAVY)
        c.drawCentredString(PAGE_W / 2, y, "CERTIFICATE")

        # "OF ACHIEVEMENT" subtitle
        y -= 1.2 * cm
        c.setFont("Helvetica", 18)
        c.setFillColor(DARK_GOLD)
        c.drawCentredString(PAGE_W / 2, y, "OF ACHIEVEMENT")

        # Decorative line
        y -= 0.6 * cm
        line_w = 8 * cm
        c.setStrokeColor(GOLD)
        c.setLineWidth(1)
        c.line(PAGE_W / 2 - line_w / 2, y, PAGE_W / 2 + line_w / 2, y)

    # --- Recipient name ---

    @staticmethod
    def _draw_recipient_name(c: Canvas, name: str) -> None:
        y = PAGE_H / 2 + 1.2 * cm

        # "This certificate is proudly presented to"
        c.setFont("Helvetica", 13)
        c.setFillColor(TEXT_MUTED)
        c.drawCentredString(PAGE_W / 2, y, "This certificate is proudly presented to")

        # Recipient name — large, bold
        y -= 1.5 * cm

        # Auto-size: shrink font if name is very long
        font_size = 32
        c.setFont("Helvetica-Bold", font_size)
        while c.stringWidth(name, "Helvetica-Bold", font_size) > PAGE_W - 8 * cm:
            font_size -= 1
            if font_size < 16:
                break

        c.setFont("Helvetica-Bold", font_size)
        c.setFillColor(NAVY)
        c.drawCentredString(PAGE_W / 2, y, name)

        # Underline below name
        y -= 0.5 * cm
        line_w = max(
            c.stringWidth(name, "Helvetica-Bold", font_size) + 2 * cm, 10 * cm
        )
        c.setStrokeColor(GOLD)
        c.setLineWidth(0.8)
        c.line(PAGE_W / 2 - line_w / 2, y, PAGE_W / 2 + line_w / 2, y)

    # --- Body (event + date) ---

    @staticmethod
    def _draw_body(c: Canvas, event_name: str, issued_date: date) -> None:
        y = PAGE_H / 2 - 2.0 * cm

        c.setFont("Helvetica", 13)
        c.setFillColor(TEXT_DARK)
        c.drawCentredString(
            PAGE_W / 2,
            y,
            "for the successful completion of",
        )

        # Event name
        y -= 1.2 * cm

        font_size = 20
        c.setFont("Helvetica-BoldOblique", font_size)
        while (
            c.stringWidth(event_name, "Helvetica-BoldOblique", font_size)
            > PAGE_W - 8 * cm
        ):
            font_size -= 1
            if font_size < 12:
                break
        c.setFont("Helvetica-BoldOblique", font_size)
        c.setFillColor(DARK_GOLD)
        c.drawCentredString(PAGE_W / 2, y, event_name)

        # Date
        y -= 1.5 * cm
        c.setFont("Helvetica", 12)
        c.setFillColor(TEXT_MUTED)
        date_str = issued_date.strftime("%B %d, %Y")
        c.drawCentredString(PAGE_W / 2, y, f"Issued on {date_str}")

    # --- Footer ---

    @staticmethod
    def _draw_footer(c: Canvas, recipient_id: uuid.UUID) -> None:
        y = 2.5 * cm

        # Certificate ID for verification
        c.setFont("Helvetica", 8)
        c.setFillColor(TEXT_MUTED)
        c.drawCentredString(PAGE_W / 2, y, f"Certificate ID: {recipient_id}")
