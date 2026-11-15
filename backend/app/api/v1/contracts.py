"""Contract ingestion, demo benchmark loader, listing, retrieval, and deletion endpoints."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_contract_or_404, run_pipeline_for_contract
from app.config import settings
from app.database import get_db
from app.models.audit import AuditLog
from app.models.contract import Contract
from app.schemas.contract_schemas import ContractDetail, ContractListItem
from app.services.demo_contracts import DEMO_CONTRACTS
from app.services.pdf_processor import process_pdf_bytes, process_text
from app.services.rag_engine import rag_engine

router = APIRouter(prefix="/contracts", tags=["Contracts"])


def _to_list_item(c: Contract) -> ContractListItem:
    redlines = c.redlines or []
    accepted_count = sum(1 for r in redlines if r.get("accepted") is True)
    return ContractListItem(
        id=c.id,
        title=c.title,
        original_filename=c.original_filename,
        status=c.status,
        playbook_name=c.playbook_name,
        overall_risk_score=float(c.overall_risk_score or 0.0),
        risk_summary=c.risk_summary or {"critical": 0, "high": 0, "medium": 0, "low": 0},
        redline_count=len(redlines),
        accepted_count=accepted_count,
        obligation_count=len(c.obligations or []),
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.post("/upload", response_model=ContractDetail)
async def upload_contract(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    playbook_name: str = Form(default="Standard Corporate Playbook"),
    auto_analyze: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Ingest a PDF or text contract, redact PII, segment sections, index RAG, and optionally analyze."""
    filename = file.filename or "uploaded_contract.pdf"
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    contract_id = str(uuid.uuid4())
    safe_name = f"{contract_id}_{Path(filename).name}"
    dest_path = Path(settings.UPLOAD_DIR) / safe_name
    dest_path.write_bytes(content)

    ext = Path(filename).suffix.lower()
    if ext == ".pdf" or content[:4] == b"%PDF":
        raw_text, sections = process_pdf_bytes(content)
    elif ext == ".docx":
        import io
        from docx import Document as DocxDocument

        docx_obj = DocxDocument(io.BytesIO(content))
        joined = "\n".join(p.text for p in docx_obj.paragraphs if p.text.strip())
        raw_text, sections = process_text(joined)
    else:
        decoded = content.decode("utf-8", errors="replace")
        raw_text, sections = process_text(decoded)

    resolved_title = (title or Path(filename).stem.replace("_", " ").replace("-", " ").title()).strip()
    contract = Contract(
        id=contract_id,
        title=resolved_title or "Uploaded Commercial Contract",
        original_filename=filename,
        file_path=str(dest_path),
        status="uploaded",
        raw_text=raw_text,
        playbook_name=playbook_name,
        extracted_sections=sections,
    )
    db.add(contract)
    await db.commit()
    await db.refresh(contract)

    rag_engine.index_contract(contract.id, sections, raw_text)

    if auto_analyze:
        contract = await run_pipeline_for_contract(contract, db)

    return contract


@router.post("/demo/{sample_type}", response_model=ContractDetail)
async def load_demo_contract(
    sample_type: str,
    playbook_name: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Instantly ingest and analyze one of the 6 benchmark contracts (ma, cloud_dpa, joint_ip, msa, saas, nda)."""
    key = sample_type.lower().strip()
    template = DEMO_CONTRACTS.get(key)
    if not template:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown demo sample '{sample_type}'. Valid samples: {', '.join(DEMO_CONTRACTS.keys())}",
        )

    raw_text, sections = process_text(template["text"])
    contract = Contract(
        title=template["title"],
        original_filename=template["filename"],
        file_path=f"demo://{key}",
        status="uploaded",
        raw_text=raw_text,
        playbook_name=playbook_name or template["playbook"],
        extracted_sections=sections,
    )
    db.add(contract)
    await db.commit()
    await db.refresh(contract)

    return await run_pipeline_for_contract(contract, db)


@router.get("", response_model=list[ContractListItem])
@router.get("/", response_model=list[ContractListItem], include_in_schema=False)
async def list_contracts(db: AsyncSession = Depends(get_db)) -> list[ContractListItem]:
    """List all contracts ordered by created_at DESC."""
    res = await db.execute(select(Contract).order_by(Contract.created_at.desc()))
    return [_to_list_item(c) for c in res.scalars().all()]


@router.get("/{contract_id}", response_model=ContractDetail)
async def get_contract(contract_id: str, db: AsyncSession = Depends(get_db)) -> Contract:
    """Return full contract analysis details, risks, debate transcript, redlines, and obligations."""
    return await get_contract_or_404(contract_id, db)


@router.delete("/{contract_id}")
async def delete_contract(contract_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Delete contract row, associated audit logs, and purge ChromaDB / RAG index."""
    contract = await get_contract_or_404(contract_id, db)

    # Purge ChromaDB / RAG collection
    rag_engine.delete_contract_index(contract_id)

    # Delete uploaded file if present locally
    if contract.file_path and not contract.file_path.startswith("demo://"):
        try:
            Path(contract.file_path).unlink(missing_ok=True)
        except Exception:
            pass

    await db.execute(delete(AuditLog).where(AuditLog.contract_id == contract_id))
    await db.delete(contract)
    await db.commit()
    return {"status": "deleted", "contract_id": contract_id}
