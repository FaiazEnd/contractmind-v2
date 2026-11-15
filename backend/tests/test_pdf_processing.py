"""Tests for PDF ingestion, PyMuPDF table extraction, PII redaction, and section segmentation."""

import io
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.pdf_processor import process_pdf_bytes, redact_pii, table_to_markdown


def test_pii_redaction_patterns():
    sample = (
        "SSN: 123-45-6789, Card: 4111-2222-3333-4444, "
        "EIN: 12-3456789, Bank Account: 987654321012."
    )
    cleaned = redact_pii(sample)
    assert "[REDACTED_SSN]" in cleaned
    assert "[REDACTED_CC]" in cleaned
    assert "[REDACTED_EIN]" in cleaned
    assert "[REDACTED_BANK_ACCT]" in cleaned
    assert "123-45-6789" not in cleaned
    assert "4111-2222-3333-4444" not in cleaned
    assert "12-3456789" not in cleaned
    assert "987654321012" not in cleaned


def test_table_to_markdown():
    rows = [["Tier", "SLA", "Fee"], ["Enterprise", "99.99%", "$120,000"]]
    md = table_to_markdown(rows)
    assert "| Tier | SLA | Fee |" in md
    assert "| --- | --- | --- |" in md
    assert "| Enterprise | 99.99% | $120,000 |" in md


def test_pymupdf_pdf_extraction_with_table_and_pii():
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Section 1. Customer Billing & Tax Identifiers", styles["Normal"]),
        Paragraph(
            "Billing contact SSN 123-45-6789 and Tax ID 98-7654321 with settlement account 1029384756.",
            styles["Normal"],
        ),
        Table(
            [["Milestone", "Amount", "Due"], ["Signing", "$50,000", "Net 30"]],
            style=TableStyle([("GRID", (0, 0), (-1, -1), 1, colors.black)]),
        ),
        Paragraph("Section 2. Limitation of Liability", styles["Normal"]),
        Paragraph("Provider aggregate liability is capped at 12 months fees.", styles["Normal"]),
    ]
    doc.build(story)

    parsed = process_pdf_bytes(buf.getvalue(), filename="test_contract.pdf")
    raw = parsed["raw_text"]
    assert "[REDACTED_SSN]" in raw
    assert "[REDACTED_EIN]" in raw
    assert "[REDACTED_BANK_ACCT]" in raw
    assert "123-45-6789" not in raw
    assert "| Milestone | Amount | Due |" in raw
    assert len(parsed["sections"]) >= 2
