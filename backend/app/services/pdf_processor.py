"""PDF ingestion, PyMuPDF table extraction, PII redaction, and section segmentation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
import pymupdf as fitz


# Ordered carefully so hyphenated/16-digit IDs are classified accurately before generic 8-17 digit bank accounts
_SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CC_PATTERN = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
_EIN_PATTERN = re.compile(r"\b\d{2}-\d{7}\b")
_BANK_ACCT_PATTERN = re.compile(r"\b\d{8,17}\b")

_SECTION_HEADER_PATTERN = re.compile(
    r"^\s*(?:(Section|Article)\s+(\d+(?:\.\d+)*)[.:\-\s]*(.*)|(\d+(?:\.\d+)*)\.\s+([A-Z][^\n]{1,120}))\s*$",
    re.IGNORECASE,
)


def redact_pii(text: str) -> str:
    """Redact SSNs, credit cards, EINs, and bank account numbers before embedding/storage."""
    if not text:
        return ""
    redacted = _SSN_PATTERN.sub("[REDACTED_SSN]", text)
    redacted = _CC_PATTERN.sub("[REDACTED_CC]", redacted)
    redacted = _EIN_PATTERN.sub("[REDACTED_EIN]", redacted)
    redacted = _BANK_ACCT_PATTERN.sub("[REDACTED_BANK_ACCT]", redacted)
    return redacted


def _clean_cell(cell: Any) -> str:
    if cell is None:
        return ""
    return re.sub(r"\s+", " ", str(cell)).strip().replace("|", "\\|")


def extract_tables_as_markdown(page: fitz.Page) -> list[str]:
    """Extract tables from a PyMuPDF page and format each as a GitHub Markdown table."""
    markdown_tables: list[str] = []
    try:
        finder = page.find_tables()
        tables = getattr(finder, "tables", finder) or []
    except Exception:
        return markdown_tables

    for table in tables:
        try:
            rows = table.extract()
        except Exception:
            continue
        if not rows or len(rows) < 1:
            continue

        cleaned_rows = [[_clean_cell(c) for c in row] for row in rows if any(c is not None and str(c).strip() for c in row)]
        if not cleaned_rows:
            continue

        col_count = max(len(r) for r in cleaned_rows)
        normalized_rows = [r + [""] * (col_count - len(r)) for r in cleaned_rows]
        header = normalized_rows[0]
        separator = ["---"] * col_count
        body = normalized_rows[1:]

        lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(separator) + " |",
        ]
        for row in body:
            lines.append("| " + " | ".join(row) + " |")
        markdown_tables.append("\n".join(lines))

    return markdown_tables


def segment_sections(pages: list[tuple[int, str]]) -> tuple[str, list[dict[str, Any]]]:
    """Segment redacted page text into structured legal sections."""
    sections: list[dict[str, Any]] = []
    current_num = "0"
    current_title = "Preamble & Parties"
    current_page = pages[0][0] if pages else 1
    current_lines: list[str] = []
    all_page_texts: list[str] = []

    def _flush() -> None:
        body = "\n".join(current_lines).strip()
        if body:
            sections.append(
                {
                    "section_number": current_num,
                    "title": current_title,
                    "text": body,
                    "page_number": current_page,
                }
            )

    for page_num, page_text in pages:
        if not page_text.strip():
            continue
        all_page_texts.append(page_text.strip())
        for line in page_text.splitlines():
            match = _SECTION_HEADER_PATTERN.match(line)
            if match:
                _flush()
                current_lines = []
                current_page = page_num
                if match.group(2):
                    current_num = match.group(2).strip()
                    current_title = (match.group(3) or f"Section {current_num}").strip(" .:-") or f"Section {current_num}"
                else:
                    current_num = match.group(4).strip()
                    current_title = (match.group(5) or f"Section {current_num}").strip(" .:-")
            else:
                current_lines.append(line)

    _flush()

    if not sections and all_page_texts:
        full = "\n\n".join(all_page_texts)
        sections.append(
            {
                "section_number": "1",
                "title": "General Terms",
                "text": full,
                "page_number": 1,
            }
        )

    raw_text = "\n\n".join(all_page_texts).strip()
    return raw_text, sections


def process_pdf_document(doc: fitz.Document) -> tuple[str, list[dict[str, Any]]]:
    """Extract text and Markdown tables from an open PyMuPDF document, then redact PII and segment."""
    pages: list[tuple[int, str]] = []
    for idx, page in enumerate(doc, start=1):
        text = page.get_text("text") or ""
        tables_md = extract_tables_as_markdown(page)
        combined = text.strip()
        if tables_md:
            combined = f"{combined}\n\n" + "\n\n".join(tables_md)
        redacted = redact_pii(combined)
        pages.append((idx, redacted))
    return segment_sections(pages)


def process_pdf(file_path: str | Path) -> tuple[str, list[dict[str, Any]]]:
    """Open a PDF file on disk and return (raw_text, sections)."""
    with fitz.open(str(file_path)) as doc:
        return process_pdf_document(doc)


def process_pdf_bytes(data: bytes) -> tuple[str, list[dict[str, Any]]]:
    """Open PDF bytes in memory and return (raw_text, sections)."""
    with fitz.open(stream=data, filetype="pdf") as doc:
        return process_pdf_document(doc)


def process_text(text: str) -> tuple[str, list[dict[str, Any]]]:
    """Redact PII and segment plain-text contract input."""
    redacted = redact_pii(text)
    return segment_sections([(1, redacted)])
