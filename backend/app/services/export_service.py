"""Word (.docx) OpenXML Track Changes and Clean Executable Export Engine."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from html import escape as xml_escape
from typing import Any

from docx import Document
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.shared import Pt, RGBColor

from app.services.diff_engine import apply_redlines_to_text, compute_diff_tokens


def _decision_label(accepted: bool | None) -> str:
    if accepted is True:
        return "ACCEPTED"
    if accepted is False:
        return "REJECTED"
    return "PENDING"


def _append_del_node(paragraph: Any, rev_id: int, ts: str, text: str) -> None:
    safe_text = xml_escape(text)
    xml = (
        f'<w:del {nsdecls("w")} w:id="{rev_id}" w:author="ContractMind Legal AI" w:date="{ts}">'
        f'<w:r><w:rPr><w:strike/><w:color w:val="DC2626"/></w:rPr>'
        f'<w:delText xml:space="preserve">{safe_text}</w:delText></w:r></w:del>'
    )
    paragraph._p.append(parse_xml(xml))


def _append_ins_node(paragraph: Any, rev_id: int, ts: str, text: str) -> None:
    safe_text = xml_escape(text)
    xml = (
        f'<w:ins {nsdecls("w")} w:id="{rev_id}" w:author="ContractMind Legal AI" w:date="{ts}">'
        f'<w:r><w:rPr><w:u w:val="single"/><w:color w:val="16A34A"/></w:rPr>'
        f'<w:t xml:space="preserve">{safe_text}</w:t></w:r></w:ins>'
    )
    paragraph._p.append(parse_xml(xml))


def export_to_docx(contract: Any) -> bytes:
    """Export contract redlines as a .docx document with native OpenXML Track Changes."""
    doc = Document()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    title = getattr(contract, "title", "ContractMind Legal Review")
    playbook = getattr(contract, "playbook_name", "Standard Corporate Playbook")
    risk_score = getattr(contract, "overall_risk_score", 0.0)
    redlines = getattr(contract, "redlines", None) or []

    heading = doc.add_heading(f"ContractMind v2.0 — Track Changes Redline Package", level=0)
    heading.runs[0].font.color.rgb = RGBColor(0x1D, 0x1A, 0x18)

    meta = doc.add_paragraph()
    meta.add_run(f"Agreement: {title}\n").bold = True
    meta.add_run(f"Playbook: {playbook}  |  Composite Risk Severity: {risk_score}/100  |  Generated: {ts}\n")

    # Overview Summary Table
    doc.add_heading("Executive Redline Summary", level=1)
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Section"
    hdr_cells[1].text = "Severity"
    hdr_cells[2].text = "Redline Type"
    hdr_cells[3].text = "Decision Status"
    for cell in hdr_cells:
        for p in cell.paragraphs:
            for r in p.runs:
                r.bold = True

    for rl in redlines:
        row_cells = table.add_row().cells
        row_cells[0].text = f"Section {rl.get('section_number', 'General')}"
        row_cells[1].text = str(rl.get("risk_severity", "MEDIUM"))
        row_cells[2].text = str(rl.get("diff_type", "modification")).title()
        row_cells[3].text = _decision_label(rl.get("accepted"))

    # Detailed Clause Revisions
    doc.add_heading("Detailed Clause Revisions (OpenXML Track Changes)", level=1)
    rev_counter = 1

    if not redlines:
        doc.add_paragraph("No high-risk clauses required redlining in this agreement.")
    else:
        for rl in redlines:
            sec_num = rl.get("section_number", "General")
            severity = rl.get("risk_severity", "MEDIUM")
            accepted = rl.get("accepted")
            status_label = _decision_label(accepted)
            rationale = rl.get("legal_rationale", "")

            doc.add_heading(f"Section {sec_num} — [{severity}] ({status_label})", level=2)
            if rationale:
                rat_p = doc.add_paragraph()
                rat_run = rat_p.add_run(f"Legal Rationale: {rationale}")
                rat_run.italic = True
                rat_run.font.size = Pt(9.5)
                rat_run.font.color.rgb = RGBColor(0x57, 0x53, 0x4E)

            clause_p = doc.add_paragraph()
            orig_text = rl.get("original_text", "")
            sugg_text = rl.get("suggested_text", "")

            if accepted is False:
                # Rejected: retain original text cleanly without Track Changes markup
                clause_p.add_run(orig_text)
                note = doc.add_paragraph()
                note_run = note.add_run("[Decision: Rejected — Original clause retained]")
                note_run.font.size = Pt(8.5)
                note_run.font.color.rgb = RGBColor(0x78, 0x71, 0x6C)
            else:
                tokens = rl.get("diff_tokens") or compute_diff_tokens(orig_text, sugg_text)
                for tok in tokens:
                    t_type = tok.get("type", "equal")
                    t_text = tok.get("text", "")
                    if not t_text:
                        continue
                    if t_type == "equal":
                        clause_p.add_run(t_text)
                    elif t_type == "del":
                        _append_del_node(clause_p, rev_counter, ts, t_text)
                        rev_counter += 1
                    elif t_type == "ins":
                        _append_ins_node(clause_p, rev_counter, ts, t_text)
                        rev_counter += 1

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def export_clean_docx(contract: Any, include_pending: bool = False) -> bytes:
    """Export a clean execution-ready .docx with accepted redlines baked in and zero diff markup."""
    doc = Document()
    title = getattr(contract, "title", "Executed Agreement")
    sections = getattr(contract, "extracted_sections", None) or []
    redlines = getattr(contract, "redlines", None) or []
    raw_text = getattr(contract, "raw_text", "") or ""

    heading = doc.add_heading(title, level=0)
    heading.runs[0].font.color.rgb = RGBColor(0x1D, 0x1A, 0x18)

    sub = doc.add_paragraph()
    sub_run = sub.add_run("CLEAN EXECUTION DRAFT — Prepared by ContractMind v2.0")
    sub_run.font.size = Pt(9.5)
    sub_run.font.color.rgb = RGBColor(0x78, 0x71, 0x6C)

    if sections:
        baked_sections = apply_redlines_to_text(
            sections,
            redlines,
            accepted_only=not include_pending,
        )
        for sec in baked_sections:
            sec_num = sec.get("section_number", "")
            sec_title = sec.get("title", "")
            sec_text = sec.get("text", "")
            header_text = f"Section {sec_num}: {sec_title}" if sec_num != "0" else sec_title
            doc.add_heading(header_text, level=1)
            for para in sec_text.split("\n\n"):
                if para.strip():
                    doc.add_paragraph(para.strip())
    else:
        text_out = raw_text
        for rl in redlines:
            if (rl.get("accepted") is True) or (include_pending and rl.get("accepted") is None):
                orig = rl.get("original_text", "")
                sugg = rl.get("suggested_text", "")
                if orig and sugg and orig in text_out:
                    text_out = text_out.replace(orig, sugg, 1)
        for para in text_out.split("\n\n"):
            if para.strip():
                doc.add_paragraph(para.strip())

    # Signature Block
    doc.add_heading("IN WITNESS WHEREOF", level=1)
    sig_table = doc.add_table(rows=2, cols=2)
    sig_table.cell(0, 0).text = "PARTY A (CUSTOMER / ENTERPRISE)"
    sig_table.cell(0, 1).text = "PARTY B (COUNTERPARTY / VENDOR)"
    sig_table.cell(1, 0).text = "\nBy: ___________________________\nName:\nTitle:\nDate:"
    sig_table.cell(1, 1).text = "\nBy: ___________________________\nName:\nTitle:\nDate:"

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
