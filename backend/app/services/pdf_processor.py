"""PDF ingestion, PyMuPDF table extraction, PII redaction, and clause segmentation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover
    fitz = None  # type: ignore[assignment]


# Order matters: specific hyphenated/grouped formats before generic 8-17 digit bank accounts
PII_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
    (re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b"), "[REDACTED_CC]"),
    (re.compile(r"\b\d{2}-\d{7}\b"), "[REDACTED_EIN]"),
    (re.compile(r"\b\d{8,17}\b"), "[REDACTED_BANK_ACCT]"),
]

# Matches Section X, Article X, or numeric headers like 1., 2.1, 3.1.2 at line start
SECTION_HEADER_RE = re.compile(
    r"^\s*(?:"
    r"(?P<kw>(?:Section|SECTION|Article|ARTICLE)\s+(?:[IVXLCDM]+|\d+(?:\.\d+)*))"
    r"|(?P<num>\d+(?:\.\d+){0,3}\.?)"
    r")\s*(?:[:.\-–—]\s*|\s+)(?P<title>[A-Z][^\n]{1,120})?\s*$"
)


def redact_pii(text: str) -> str:
    """Redact SSN, credit card, EIN, and bank account numbers from text."""
    if not text:
        return ""
    cleaned = text
    for pattern, token in PII_PATTERNS:
        cleaned = pattern.sub(token, cleaned)
    return cleaned


def table_to_markdown(rows: List[List[Any]]) -> str:
    """Convert extracted table rows into a valid GitHub Markdown table."""
    if not rows:
        return ""

    def _clean_cell(cell: Any) -> str:
        if cell is None:
            return ""
        return " ".join(str(cell).replace("|", "\\|").split())

    cleaned_rows = [[_clean_cell(c) for c in row] for row in rows if any(c is not None and str(c).strip() for c in row)]
    if not cleaned_rows:
        return ""

    col_count = max(len(r) for r in cleaned_rows)
    padded = [r + [""] * (col_count - len(r)) for r in cleaned_rows]

    header = padded[0]
    separator = ["---"] * col_count
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    for row in padded[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def segment_sections(pages: List[Tuple[int, str]]) -> List[Dict[str, Any]]:
    """Segment contract pages into structured sections matching Section/Article/numeric headers."""
    sections: List[Dict[str, Any]] = []
    current_num = "1"
    current_title = "Preamble & General Terms"
    current_page = pages[0][0] if pages else 1
    buffer: List[str] = []

    def _flush() -> None:
        body = "\n".join(buffer).strip()
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
        for line in page_text.splitlines():
            stripped = line.strip()
            match = SECTION_HEADER_RE.match(stripped)
            # Guard against matching standalone numbers like "100." inside normal prose
            is_heading = False
            if match:
                if match.group("kw"):
                    is_heading = True
                elif match.group("num") and match.group("title"):
                    num_clean = match.group("num").rstrip(".")
                    first_part = int(num_clean.split(".")[0])
                    if first_part <= 50 and len(match.group("title").strip()) >= 3:
                        is_heading = True

            if is_heading and match:
                _flush()
                buffer = []
                raw_num = (match.group("kw") or match.group("num") or "").strip().rstrip(".")
                # Normalize "Section 3" -> "3", "Article II" -> "Article II"
                norm_match = re.match(r"^(?:Section|SECTION)\s+(.+)$", raw_num)
                current_num = norm_match.group(1) if norm_match else raw_num
                current_title = (match.group("title") or f"Section {current_num}").strip(" .:-")
                current_page = page_num
            else:
                buffer.append(line)

    _flush()

    if not sections:
        combined = "\n".join(p[1] for p in pages).strip()
        if combined:
            sections.append(
                {
                    "section_number": "1",
                    "title": "Agreement Terms",
                    "text": combined,
                    "page_number": 1,
                }
            )
    return sections


def process_text_document(raw_text: str) -> Dict[str, Any]:
    """Redact PII and segment plain text into structured sections."""
    redacted = redact_pii(raw_text)
    sections = segment_sections([(1, redacted)])
    return {"raw_text": redacted, "sections": sections}


def process_pdf_bytes(file_bytes: bytes, filename: str = "contract.pdf") -> Dict[str, Any]:
    """Extract text and tables from PDF bytes using PyMuPDF, redact PII, and segment sections."""
    lower = filename.lower()
    if not lower.endswith(".pdf") and not file_bytes.lstrip().startswith(b"%PDF"):
        decoded = file_bytes.decode("utf-8", errors="replace")
        return process_text_document(decoded)

    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is required to parse PDF documents.")

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages: List[Tuple[int, str]] = []
    try:
        for idx, page in enumerate(doc, start=1):
            page_parts: List[str] = []
            text = page.get_text("text") or ""
            if text.strip():
                page_parts.append(text.strip())

            # Extract structured tables into GitHub Markdown
            try:
                finder = page.find_tables()
                tables = getattr(finder, "tables", []) or []
                for tbl in tables:
                    extracted = tbl.extract()
                    md_table = table_to_markdown(extracted)
                    if md_table:
                        page_parts.append(f"\n{md_table}\n")
            except Exception:
                # Non-fatal if a specific page has malformed table geometry
                pass

            redacted_page = redact_pii("\n".join(page_parts))
            pages.append((idx, redacted_page))
    finally:
        doc.close()

    raw_text = "\n\n".join(p[1] for p in pages if p[1].strip()).strip()
    sections = segment_sections(pages)
    return {"raw_text": raw_text, "sections": sections}


def process_pdf_file(path: str | Path) -> Dict[str, Any]:
    """Read a PDF or text file from disk and extract redacted text and sections."""
    file_path = Path(path)
    return process_pdf_bytes(file_path.read_bytes(), filename=file_path.name)
