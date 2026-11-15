"""Tests for PyMuPDF PDF ingestion, Markdown table extraction, PII redaction, and section segmentation."""

from __future__ import annotations

import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

from app.services.pdf_processor import process_pdf_bytes, redact_pii


def test_pii_redactor_removes_all_sensitive_patterns() -> None:
    sample = (
        "Signer SSN: 123-45-6789, Corporate Card: 4111-2222-3333-4444, "
        "Company EIN: 12-3456789, Escrow Account: 987654321012."
    )
    redacted = redact_pii(sample)
    assert "123-45-6789" not in redacted
    assert "4111-2222-3333-4444" not in redacted
    assert "12-3456789" not in redacted
    assert "987654321012" not in redacted
    assert "[REDACTED_SSN]" in redacted
    assert "[REDACTED_CC]" in redacted
    assert "[REDACTED_EIN]" in redacted
    assert "[REDACTED_BANK_ACCT]" in redacted


def test_pymupdf_pdf_table_extraction_and_segmentation() -> None:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Section 1. Pricing Schedule", styles["Normal"]),
        Paragraph("Customer SSN 123-45-6789 shall pay net 30 days per table below.", styles["Normal"]),
        Table(
            [["Tier", "Annual Fee", "SLA"], ["Enterprise", "$120,000", "99.9%"]],
            style=TableStyle([("GRID", (0, 0), (-1, -1), 1, colors.black)]),
        ),
        Paragraph("Section 2. Liability", styles["Normal"]),
        Paragraph("Vendor provides uncapped indemnification without any cap.", styles["Normal"]),
    ]
    doc.build(story)

    raw_text, sections = process_pdf_bytes(buf.getvalue())
    assert "[REDACTED_SSN]" in raw_text
    assert "123-45-6789" not in raw_text
    assert "| Tier | Annual Fee | SLA |" in raw_text
    assert "| Enterprise | $120,000 | 99.9% |" in raw_text
    assert len(sections) >= 2
    assert any(s["section_number"] == "1" for s in sections)
    assert any(s["section_number"] == "2" for s in sections)
