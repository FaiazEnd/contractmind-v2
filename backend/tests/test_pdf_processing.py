"""Tests for PyMuPDF table extraction to Markdown, PII redaction, and section segmentation."""
from __future__ import annotations

import io
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.pdf_processor import process_document_bytes, redact_pii


def test_pii_redactor_removes_all_sensitive_patterns() -> None:
    sample = (
        "Signer SSN: 123-45-6789. Corporate EIN: 12-3456789. "
        "Card: 4111-2222-3333-4444. Wire Account: 987654321012."
    )
    redacted = redact_pii(sample)
    assert "123-45-6789" not in redacted
    assert "12-3456789" not in redacted
    assert "4111-2222-3333-4444" not in redacted
    assert "987654321012" not in redacted
    assert "[REDACTED_SSN]" in redacted
    assert "[REDACTED_EIN]" in redacted
    assert "[REDACTED_CC]" in redacted
    assert "[REDACTED_BANK_ACCT]" in redacted


def test_pymupdf_extracts_markdown_table_and_redacts_pii() -> None:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Section 1. Payment Schedule and Identity", styles["Normal"]),
        Paragraph(
            "Vendor Tax EIN is 98-7654321 and Contact SSN is 555-44-3333.",
            styles["Normal"],
        ),
    ]
    tbl = Table(
        [
            ["Milestone", "Fee", "Due"],
            ["Phase 1", "$50,000", "Net 30"],
            ["Phase 2", "$75,000", "Net 45"],
        ]
    )
    tbl.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ]
        )
    )
    story.append(tbl)
    story.append(Paragraph("Section 2. Limitation of Liability", styles["Normal"]))
    story.append(
        Paragraph("Provider liability shall be capped at 12 months fees.", styles["Normal"])
    )
    doc.build(story)

    result = process_document_bytes(buf.getvalue(), "test_table_contract.pdf")
    raw = result["raw_text"]
    assert "[REDACTED_EIN]" in raw
    assert "[REDACTED_SSN]" in raw
    assert "98-7654321" not in raw
    assert "| Milestone | Fee | Due |" in raw
    assert "| --- | --- | --- |" in raw
    assert "| Phase 1 | $50,000 | Net 30 |" in raw
    assert len(result["sections"]) >= 2
