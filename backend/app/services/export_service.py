"""Word (.docx) OpenXML Track Changes & Clean Executable export engine."""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches, Pt, RGBColor


AUTHOR_NAME = "ContractMind Legal AI"


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _decision_label(accepted: bool | None) -> str:
    if accepted is True:
        return "Accepted"
    if accepted is False:
        return "Rejected"
    return "Pending"


def _append_plain_run(paragraph: Any, text: str) -> None:
    if not text:
        return
    run = paragraph.add_run(text)
    run.font.size = Pt(10.5)
    run.font.name = "Calibri"


def _append_w_del(paragraph: Any, rev_id: int, ts: str, text: str) -> None:
    """Inject native OpenXML <w:del> track changes deletion element."""
    if not text:
        return
    del_el = OxmlElement("w:del")
    del_el.set(qn("w:id"), str(rev_id))
    del_el.set(qn("w:author"), AUTHOR_NAME)
    del_el.set(qn("w:date"), ts)

    r_el = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    rpr.append(OxmlElement("w:strike"))
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "DC2626")
    rpr.append(color)
    r_el.append(rpr)

    del_text = OxmlElement("w:delText")
    del_text.set(qn("xml:space"), "preserve")
    del_text.text = text
    r_el.append(del_text)
    del_el.append(r_el)

    paragraph._p.append(del_el)


def _append_w_ins(paragraph: Any, rev_id: int, ts: str, text: str) -> None:
    """Inject native OpenXML <w:ins> track changes insertion element."""
    if not text:
        return
    ins_el = OxmlElement("w:ins")
    ins_el.set(qn("w:id"), str(rev_id))
    ins_el.set(qn("w:author"), AUTHOR_NAME)
    ins_el.set(qn("w:date"), ts)

    r_el = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    u_el = OxmlElement("w:u")
    u_el.set(qn("w:val"), "single")
    rpr.append(u_el)
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "16A34A")
    rpr.append(color)
    r_el.append(rpr)

    t_el = OxmlElement("w:t")
    t_el.set(qn("xml:space"), "preserve")
    t_el.text = text
    r_el.append(t_el)
    ins_el.append(r_el)

    paragraph._p.append(ins_el)


def _enable_track_revisions(doc: Document) -> None:
    """Enable <w:trackRevisions/> in document settings so Word opens with Track Changes active."""
    settings_el = doc.settings.element
    if settings_el.find(qn("w:trackRevisions")) is None:
        settings_el.append(parse_xml(f'<w:trackRevisions {nsdecls("w")}/>'))


def export_to_docx(contract: Any) -> bytes:
    """Generate a .docx file containing a summary table and native OpenXML Track Changes."""
    doc = Document()
    _enable_track_revisions(doc)

    ts = _iso_utc_now()
    title = getattr(contract, "title", "Contract Agreement")
    playbook = getattr(contract, "playbook_name", "Standard Corporate Playbook")
    risk_score = getattr(contract, "overall_risk_score", 0.0)
    redlines: list[dict[str, Any]] = list(getattr(contract, "redlines", None) or [])
    sections: list[dict[str, Any]] = list(getattr(contract, "extracted_sections", None) or [])

    # Document Header
    heading = doc.add_heading(f"{title} — Legal Redline Review", level=0)
    heading.alignment = WD_ALIGN_PARAGRAPH.LEFT

    meta = doc.add_paragraph()
    meta_run = meta.add_run(
        f"Playbook: {playbook}  |  Composite Risk Score: {risk_score}/100  |  Generated: {ts}"
    )
    meta_run.font.size = Pt(9.5)
    meta_run.font.color.rgb = RGBColor(0x78, 0x71, 0x6C)

    # Redline Overview Table
    doc.add_heading("Redline Decision Summary", level=1)
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    headers = ["Section", "Severity", "Redline Type", "Decision Status"]
    for idx, label in enumerate(headers):
        cell = table.rows[0].cells[idx]
        cell.text = label
        for p in cell.paragraphs:
            for r in p.runs:
                r.bold = True
                r.font.size = Pt(9.5)

    for rl in redlines:
        row_cells = table.add_row().cells
        row_cells[0].text = f"Section {rl.get('section_number', '?')}"
        row_cells[1].text = str(rl.get("risk_severity", "MEDIUM")).upper()
        row_cells[2].text = str(rl.get("diff_type", "modification")).title()
        row_cells[3].text = _decision_label(rl.get("accepted"))

    # Detailed Clause-by-Clause Track Changes
    doc.add_heading("Clause-by-Clause Track Changes", level=1)
    redline_by_section: dict[str, list[dict[str, Any]]] = {}
    for rl in redlines:
        sec_key = str(rl.get("section_number", "")).strip()
        redline_by_section.setdefault(sec_key, []).append(rl)

    rev_counter = 1

    if sections:
        for sec in sections:
            sec_num = str(sec.get("section_number", "")).strip()
            sec_title = str(sec.get("title", "Clause")).strip()
            sec_text = str(sec.get("text", "")).strip()
            sec_redlines = redline_by_section.get(sec_num, [])

            if sec_redlines:
                status_tags = ", ".join(
                    f"{rl.get('risk_severity', 'MEDIUM')}: {_decision_label(rl.get('accepted'))}"
                    for rl in sec_redlines
                )
                doc.add_heading(
                    f"Section {sec_num}: {sec_title} [{status_tags}]", level=2
                )
                for rl in sec_redlines:
                    accepted = rl.get("accepted")
                    rationale = rl.get("legal_rationale", "")
                    if rationale:
                        rp = doc.add_paragraph()
                        rr = rp.add_run(f"Legal Rationale ({_decision_label(accepted)}): {rationale}")
                        rr.italic = True
                        rr.font.size = Pt(9)
                        rr.font.color.rgb = RGBColor(0x8E, 0x53, 0x33)

                    p = doc.add_paragraph()
                    if accepted is False:
                        # Rejected redline: retain original text cleanly
                        _append_plain_run(p, rl.get("original_text", sec_text))
                    else:
                        # Accepted or Pending: render native OpenXML Track Changes
                        tokens = rl.get("diff_tokens") or []
                        if tokens:
                            for tok in tokens:
                                t_type = tok.get("type", "equal")
                                t_val = tok.get("text", "")
                                if t_type == "equal":
                                    _append_plain_run(p, t_val)
                                elif t_type == "delete":
                                    _append_w_del(p, rev_counter, ts, t_val)
                                    rev_counter += 1
                                elif t_type == "insert":
                                    _append_w_ins(p, rev_counter, ts, t_val)
                                    rev_counter += 1
                        else:
                            _append_w_del(
                                p, rev_counter, ts, rl.get("original_text", "")
                            )
                            rev_counter += 1
                            _append_w_ins(
                                p, rev_counter, ts, rl.get("suggested_text", "")
                            )
                            rev_counter += 1
            else:
                doc.add_heading(f"Section {sec_num}: {sec_title}", level=2)
                p = doc.add_paragraph()
                _append_plain_run(p, sec_text)
    else:
        for rl in redlines:
            sec_num = rl.get("section_number", "?")
            doc.add_heading(
                f"Section {sec_num} [{_decision_label(rl.get('accepted'))}]", level=2
            )
            p = doc.add_paragraph()
            if rl.get("accepted") is False:
                _append_plain_run(p, rl.get("original_text", ""))
            else:
                for tok in rl.get("diff_tokens") or []:
                    t_type = tok.get("type", "equal")
                    t_val = tok.get("text", "")
                    if t_type == "equal":
                        _append_plain_run(p, t_val)
                    elif t_type == "delete":
                        _append_w_del(p, rev_counter, ts, t_val)
                        rev_counter += 1
                    elif t_type == "insert":
                        _append_w_ins(p, rev_counter, ts, t_val)
                        rev_counter += 1

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


def export_clean_docx(contract: Any) -> bytes:
    """Generate a clean execution-ready .docx baking in accepted redlines with zero markup tags."""
    doc = Document()
    title = getattr(contract, "title", "Contract Agreement")
    playbook = getattr(contract, "playbook_name", "Standard Corporate Playbook")
    redlines: list[dict[str, Any]] = list(getattr(contract, "redlines", None) or [])
    sections: list[dict[str, Any]] = list(getattr(contract, "extracted_sections", None) or [])

    accepted_count = sum(1 for r in redlines if r.get("accepted") is True)
    heading = doc.add_heading(title, level=0)
    heading.alignment = WD_ALIGN_PARAGRAPH.LEFT

    subtitle = doc.add_paragraph()
    sub_run = subtitle.add_run(
        f"Clean Execution Draft  |  Playbook: {playbook}  |  {accepted_count} Accepted Revision(s) Incorporated"
    )
    sub_run.font.size = Pt(9.5)
    sub_run.font.color.rgb = RGBColor(0x57, 0x53, 0x4E)

    redline_by_section: dict[str, list[dict[str, Any]]] = {}
    for rl in redlines:
        sec_key = str(rl.get("section_number", "")).strip()
        redline_by_section.setdefault(sec_key, []).append(rl)

    if sections:
        for sec in sections:
            sec_num = str(sec.get("section_number", "")).strip()
            sec_title = str(sec.get("title", "Clause")).strip()
            sec_text = str(sec.get("text", "")).strip()
            sec_redlines = redline_by_section.get(sec_num, [])

            doc.add_heading(f"Section {sec_num}: {sec_title}", level=2)
            if sec_redlines:
                # Apply accepted redlines cleanly; retain original text for rejected or pending ones
                final_parts: list[str] = []
                for rl in sec_redlines:
                    if rl.get("accepted") is True:
                        final_parts.append(str(rl.get("suggested_text", sec_text)).strip())
                    else:
                        final_parts.append(str(rl.get("original_text", sec_text)).strip())
                body_text = "\n\n".join(part for part in final_parts if part)
            else:
                body_text = sec_text

            p = doc.add_paragraph()
            _append_plain_run(p, body_text)
    else:
        for rl in redlines:
            doc.add_heading(f"Section {rl.get('section_number', '?')}", level=2)
            p = doc.add_paragraph()
            chosen = (
                rl.get("suggested_text", "")
                if rl.get("accepted") is True
                else rl.get("original_text", "")
            )
            _append_plain_run(p, str(chosen))

    # Execution signature block
    doc.add_heading("IN WITNESS WHEREOF", level=2)
    sig = doc.add_paragraph(
        "The parties hereto have caused this Agreement to be executed by their duly authorized representatives."
    )
    sig.paragraph_format.space_before = Pt(6)
    doc.add_paragraph("Company Authorized Signatory: ___________________________    Date: _______________")
    doc.add_paragraph("Counterparty Authorized Signatory: ______________________    Date: _______________")

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()
