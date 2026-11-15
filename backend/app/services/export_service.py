"""Word (.docx) OpenXML Track Changes and Clean Executable Export Engine."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any, Dict, List

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from lxml import etree

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"


def _w_tag(local_name: str) -> str:
    return f"{{{W_NS}}}{local_name}"


def _decision_label(accepted: Any) -> str:
    if accepted is True:
        return "Accepted"
    if accepted is False:
        return "Rejected"
    return "Pending Review"


def _append_run(paragraph: Any, text: str, color_hex: str | None = None, strike: bool = False, underline: bool = False) -> None:
    if not text:
        return
    r = etree.SubElement(paragraph._p, _w_tag("r"))
    if color_hex or strike or underline:
        rPr = etree.SubElement(r, _w_tag("rPr"))
        if strike:
            etree.SubElement(rPr, _w_tag("strike"))
        if underline:
            u = etree.SubElement(rPr, _w_tag("u"))
            u.set(_w_tag("val"), "single")
        if color_hex:
            c = etree.SubElement(rPr, _w_tag("color"))
            c.set(_w_tag("val"), color_hex)
    t = etree.SubElement(r, _w_tag("t"))
    t.set(f"{{{XML_NS}}}space", "preserve")
    t.text = text


def _append_w_del(paragraph: Any, rev_id: int, ts: str, text: str) -> None:
    if not text:
        return
    w_del = etree.SubElement(paragraph._p, _w_tag("del"))
    w_del.set(_w_tag("id"), str(rev_id))
    w_del.set(_w_tag("author"), "ContractMind Legal AI")
    w_del.set(_w_tag("date"), ts)
    r = etree.SubElement(w_del, _w_tag("r"))
    rPr = etree.SubElement(r, _w_tag("rPr"))
    etree.SubElement(rPr, _w_tag("strike"))
    c = etree.SubElement(rPr, _w_tag("color"))
    c.set(_w_tag("val"), "DC2626")
    del_text = etree.SubElement(r, _w_tag("delText"))
    del_text.set(f"{{{XML_NS}}}space", "preserve")
    del_text.text = text


def _append_w_ins(paragraph: Any, rev_id: int, ts: str, text: str) -> None:
    if not text:
        return
    w_ins = etree.SubElement(paragraph._p, _w_tag("ins"))
    w_ins.set(_w_tag("id"), str(rev_id))
    w_ins.set(_w_tag("author"), "ContractMind Legal AI")
    w_ins.set(_w_tag("date"), ts)
    r = etree.SubElement(w_ins, _w_tag("r"))
    rPr = etree.SubElement(r, _w_tag("rPr"))
    u = etree.SubElement(rPr, _w_tag("u"))
    u.set(_w_tag("val"), "single")
    c = etree.SubElement(rPr, _w_tag("color"))
    c.set(_w_tag("val"), "16A34A")
    t = etree.SubElement(r, _w_tag("t"))
    t.set(f"{{{XML_NS}}}space", "preserve")
    t.text = text


def export_to_docx(contract: Any) -> bytes:
    """Generate a .docx file with authentic OpenXML w:del / w:ins Track Changes markup."""
    doc = Document()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rev_counter = 1

    title_p = doc.add_heading(f"{contract.title} — Redline Review Draft", level=0)
    if title_p.runs:
        title_p.runs[0].font.color.rgb = RGBColor(15, 23, 42)

    meta = doc.add_paragraph()
    meta.add_run(
        f"Playbook: {contract.playbook_name}  |  Composite Risk Score: {contract.overall_risk_score}/100  |  "
        f"Generated: {ts}"
    ).font.size = Pt(9)

    redlines: List[Dict[str, Any]] = list(getattr(contract, "redlines", []) or [])
    sections: List[Dict[str, Any]] = list(getattr(contract, "extracted_sections", []) or [])

    doc.add_heading("Executive Redline Overview", level=1)
    if redlines:
        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = "Section"
        hdr_cells[1].text = "Severity"
        hdr_cells[2].text = "Redline Type"
        hdr_cells[3].text = "Decision Status"
        for cell in hdr_cells:
            for run in cell.paragraphs[0].runs:
                run.bold = True

        for rl in redlines:
            row_cells = table.add_row().cells
            row_cells[0].text = f"Section {rl.get('section_number', '?')}"
            row_cells[1].text = str(rl.get("risk_severity", "MEDIUM")).upper()
            row_cells[2].text = str(rl.get("diff_type", "modification")).title()
            row_cells[3].text = _decision_label(rl.get("accepted"))
    else:
        doc.add_paragraph("No redlines generated for this agreement.")

    doc.add_heading("Clause-by-Clause Tracked Revisions", level=1)
    redlines_by_section: Dict[str, List[Dict[str, Any]]] = {}
    for rl in redlines:
        sec_key = str(rl.get("section_number", "1"))
        redlines_by_section.setdefault(sec_key, []).append(rl)

    if sections:
        for sec in sections:
            sec_num = str(sec.get("section_number", "1"))
            sec_title = str(sec.get("title", f"Section {sec_num}"))
            sec_rls = redlines_by_section.get(sec_num, [])
            status_suffix = ""
            if sec_rls:
                statuses = ", ".join(_decision_label(r.get("accepted")) for r in sec_rls)
                status_suffix = f" [{statuses}]"
            doc.add_heading(f"Section {sec_num}: {sec_title}{status_suffix}", level=2)

            if not sec_rls:
                doc.add_paragraph(str(sec.get("text", "")))
                continue

            for rl in sec_rls:
                accepted = rl.get("accepted")
                p = doc.add_paragraph()
                if accepted is False:
                    # Rejected: preserve original contract text without Track Changes markup
                    _append_run(p, str(rl.get("original_text", sec.get("text", ""))))
                else:
                    # Accepted or Pending: emit native OpenXML Track Changes
                    tokens = rl.get("diff_tokens") or []
                    if tokens:
                        for tok in tokens:
                            t_type = tok.get("type")
                            t_text = tok.get("text", "")
                            if t_type == "del":
                                _append_w_del(p, rev_counter, ts, t_text)
                                rev_counter += 1
                            elif t_type == "ins":
                                _append_w_ins(p, rev_counter, ts, t_text)
                                rev_counter += 1
                            else:
                                _append_run(p, t_text)
                    else:
                        _append_w_del(p, rev_counter, ts, str(rl.get("original_text", "")))
                        rev_counter += 1
                        _append_w_ins(p, rev_counter, ts, str(rl.get("suggested_text", "")))
                        rev_counter += 1

                rationale = rl.get("legal_rationale")
                if rationale:
                    note = doc.add_paragraph()
                    r = note.add_run(f"Legal Rationale ({_decision_label(accepted)}): {rationale}")
                    r.italic = True
                    r.font.size = Pt(9)
                    r.font.color.rgb = RGBColor(71, 85, 105)
    else:
        for rl in redlines:
            sec_num = str(rl.get("section_number", "1"))
            doc.add_heading(f"Section {sec_num} [{_decision_label(rl.get('accepted'))}]", level=2)
            p = doc.add_paragraph()
            if rl.get("accepted") is False:
                _append_run(p, str(rl.get("original_text", "")))
            else:
                _append_w_del(p, rev_counter, ts, str(rl.get("original_text", "")))
                rev_counter += 1
                _append_w_ins(p, rev_counter, ts, str(rl.get("suggested_text", "")))
                rev_counter += 1

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def export_clean_docx(contract: Any) -> bytes:
    """Generate a clean executable .docx baking in accepted/recommended redlines without markup."""
    doc = Document()

    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    title_p = doc.add_heading(str(contract.title), level=0)
    if title_p.runs:
        title_p.runs[0].font.color.rgb = RGBColor(15, 23, 42)

    sub = doc.add_paragraph()
    sub_run = sub.add_run("CLEAN EXECUTION DRAFT — READY FOR ELECTRONIC SIGNATURE")
    sub_run.bold = True
    sub_run.font.size = Pt(9)
    sub_run.font.color.rgb = RGBColor(22, 101, 52)

    redlines: List[Dict[str, Any]] = list(getattr(contract, "redlines", []) or [])
    sections: List[Dict[str, Any]] = list(getattr(contract, "extracted_sections", []) or [])

    redlines_by_section: Dict[str, List[Dict[str, Any]]] = {}
    for rl in redlines:
        redlines_by_section.setdefault(str(rl.get("section_number", "1")), []).append(rl)

    if sections:
        for sec in sections:
            sec_num = str(sec.get("section_number", "1"))
            sec_title = str(sec.get("title", f"Section {sec_num}"))
            doc.add_heading(f"Section {sec_num}. {sec_title}", level=2)

            sec_rls = redlines_by_section.get(sec_num, [])
            if not sec_rls:
                doc.add_paragraph(str(sec.get("text", "")))
                continue

            # Replace original clause text with accepted/recommended text; keep original if rejected
            body_text = str(sec.get("text", ""))
            applied = False
            for rl in sec_rls:
                if rl.get("accepted") is False:
                    continue
                orig = str(rl.get("original_text", "")).strip()
                sugg = str(rl.get("suggested_text", "")).strip()
                if orig and orig in body_text and sugg:
                    body_text = body_text.replace(orig, sugg, 1)
                    applied = True
                elif sugg and not applied:
                    body_text = sugg
                    applied = True

            doc.add_paragraph(body_text)
    else:
        for rl in redlines:
            doc.add_heading(f"Section {rl.get('section_number', '1')}", level=2)
            final_text = (
                rl.get("original_text", "")
                if rl.get("accepted") is False
                else rl.get("suggested_text", rl.get("original_text", ""))
            )
            doc.add_paragraph(str(final_text))

    doc.add_heading("IN WITNESS WHEREOF", level=2)
    sig_table = doc.add_table(rows=3, cols=2)
    sig_table.cell(0, 0).text = "PARTY A (ENTERPRISE / CUSTOMER)"
    sig_table.cell(0, 1).text = "PARTY B (VENDOR / COUNTERPARTY)"
    sig_table.cell(1, 0).text = "Signature: ___________________________"
    sig_table.cell(1, 1).text = "Signature: ___________________________"
    sig_table.cell(2, 0).text = "Name / Title / Date: ___________________"
    sig_table.cell(2, 1).text = "Name / Title / Date: ___________________"

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
