"""PDF ingestion, PyMuPDF table extraction to Markdown, PII redaction, and section segmentation."""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF


# Ordered carefully so hyphenated/formatted patterns match before generic digit sequences
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
EIN_PATTERN = re.compile(r"\b\d{2}-\d{7}\b")
CREDIT_CARD_PATTERN = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
BANK_ACCT_PATTERN = re.compile(r"\b\d{8,17}\b")

SECTION_HEADER_PATTERN = re.compile(
    r"^\s*(?:(?P<prefix>Section|Article|SECTION|ARTICLE)\s+(?P<num1>[IVXLCDM]+|\d+(?:\.\d+)*)|(?P<num2>\d+(?:\.\d+)+|\d+\.))\s*(?:[:.\-\u2013\u2014]?\s*(?P<title>[A-Za-z][^\n]{1,100}))?$",
    re.MULTILINE,
)


def redact_pii(text: str) -> str:
    """Redact US SSNs, EINs, credit card numbers, and bank account numbers."""
    if not text:
        return ""
    redacted = SSN_PATTERN.sub("[REDACTED_SSN]", text)
    redacted = EIN_PATTERN.sub("[REDACTED_EIN]", redacted)
    redacted = CREDIT_CARD_PATTERN.sub("[REDACTED_CC]", redacted)
    redacted = BANK_ACCT_PATTERN.sub("[REDACTED_BANK_ACCT]", redacted)
    return redacted


def _format_table_markdown(rows: list[list[Any]]) -> str:
    """Convert extracted table rows into a valid GitHub Flavored Markdown table."""
    if not rows:
        return ""
    cleaned_rows: list[list[str]] = []
    max_cols = 0
    for row in rows:
        cells = [
            " ".join(str(cell or "").split()).replace("|", "\\|") for cell in row
        ]
        if any(cells):
            cleaned_rows.append(cells)
            max_cols = max(max_cols, len(cells))

    if not cleaned_rows or max_cols == 0:
        return ""

    # Pad rows to uniform width
    normalized = [r + [""] * (max_cols - len(r)) for r in cleaned_rows]
    header = normalized[0]
    separator = ["---"] * max_cols
    body = normalized[1:] if len(normalized) > 1 else []

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    for row in body:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def extract_pdf_pages(file_bytes: bytes) -> list[dict[str, Any]]:
    """Extract text and Markdown tables from each page of a PDF using PyMuPDF."""
    pages_data: list[dict[str, Any]] = []
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for idx, page in enumerate(doc, start=1):
            page_text = page.get_text("text") or ""
            markdown_tables: list[str] = []
            try:
                tables = page.find_tables()
                if tables and getattr(tables, "tables", None):
                    for tbl in tables.tables:
                        extracted = tbl.extract()
                        md = _format_table_markdown(extracted)
                        if md:
                            markdown_tables.append(md)
            except Exception:
                # Some PDF versions/pages may not yield structured tables cleanly
                markdown_tables = []

            combined = page_text.strip()
            if markdown_tables:
                combined = (
                    combined
                    + "\n\n"
                    + "\n\n".join(markdown_tables)
                ).strip()

            pages_data.append(
                {
                    "page_number": idx,
                    "text": redact_pii(combined),
                    "tables": markdown_tables,
                }
            )
    return pages_data


def segment_sections(
    pages_data: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """Segment extracted text into structured clauses matching Section X, Article X, or numeric headers."""
    full_text = "\n\n".join(p["text"] for p in pages_data if p.get("text")).strip()
    if not full_text:
        return "", []

    # Build character offset -> page number map
    page_offsets: list[tuple[int, int, int]] = []
    cursor = 0
    for p in pages_data:
        txt = p.get("text") or ""
        if not txt:
            continue
        start = cursor
        end = start + len(txt)
        page_offsets.append((start, end, p["page_number"]))
        cursor = end + 2  # "\n\n"

    def _page_for_offset(pos: int) -> int:
        for start, end, pnum in page_offsets:
            if start <= pos <= end:
                return pnum
        return page_offsets[-1][2] if page_offsets else 1

    matches = list(SECTION_HEADER_PATTERN.finditer(full_text))
    sections: list[dict[str, Any]] = []

    if not matches:
        sections.append(
            {
                "section_number": "1",
                "title": "Agreement Terms",
                "text": full_text,
                "page_number": 1,
            }
        )
        return full_text, sections

    # Include preamble before first header if meaningful
    first_start = matches[0].start()
    preamble = full_text[:first_start].strip()
    if len(preamble) > 40:
        sections.append(
            {
                "section_number": "0",
                "title": "Preamble & Parties",
                "text": preamble,
                "page_number": 1,
            }
        )

    for i, m in enumerate(matches):
        raw_num = (m.group("num1") or m.group("num2") or str(i + 1)).rstrip(".")
        title = (m.group("title") or "").strip()
        if not title:
            title = f"Clause {raw_num}"

        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        body = full_text[body_start:body_end].strip()
        header_line = m.group(0).strip()
        section_text = f"{header_line}\n{body}".strip() if body else header_line

        sections.append(
            {
                "section_number": raw_num,
                "title": title,
                "text": section_text,
                "page_number": _page_for_offset(m.start()),
            }
        )

    return full_text, sections


def process_document_bytes(
    file_bytes: bytes, filename: str
) -> dict[str, Any]:
    """Process uploaded PDF, DOCX, or plain text bytes into redacted text and structured sections."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        pages_data = extract_pdf_pages(file_bytes)
    elif ext == ".docx":
        import docx

        doc = docx.Document(io.BytesIO(file_bytes))
        parts: list[str] = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            rows = [[cell.text for cell in row.cells] for row in table.rows]
            md = _format_table_markdown(rows)
            if md:
                parts.append(md)
        text = redact_pii("\n\n".join(parts))
        pages_data = [{"page_number": 1, "text": text, "tables": []}]
    else:
        decoded = file_bytes.decode("utf-8", errors="replace")
        pages_data = [{"page_number": 1, "text": redact_pii(decoded), "tables": []}]

    raw_text, sections = segment_sections(pages_data)
    return {
        "raw_text": raw_text,
        "sections": sections,
        "page_count": len(pages_data),
    }


def process_raw_text(text: str) -> dict[str, Any]:
    """Process plain contract text (used for demo benchmarks) through PII redaction & segmentation."""
    clean = redact_pii(text)
    pages_data = [{"page_number": 1, "text": clean, "tables": []}]
    raw_text, sections = segment_sections(pages_data)
    return {
        "raw_text": raw_text,
        "sections": sections,
        "page_count": 1,
    }
