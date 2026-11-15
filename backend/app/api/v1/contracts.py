"""Contracts API endpoints: upload, demo corpus loading, listing, detail, and deletion."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import run_contract_analysis
from app.config import settings
from app.database import get_db
from app.models.audit import AuditLog
from app.models.contract import Contract
from app.schemas.contract_schemas import ContractDetail, ContractListItem
from app.services.demo_contracts import DEMO_CONTRACTS
from app.services.pdf_processor import process_pdf_bytes, process_text_document
from app.services.rag_engine import rag_engine

router = APIRouter()


@router.post("/upload", response_model=ContractDetail, status_code=status.HTTP_201_CREATED)
async def upload_contract(
    file: UploadFile = File(...),
    title: Optional[str] = Form(default=None),
    playbook_name: str = Form(default="Standard Corporate Playbook"),
    auto_analyze: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> Contract:
    """Upload a PDF or text contract, redact PII, segment sections, and index into RAG."""
    filename = file.filename or "uploaded_contract.pdf"
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    contract_id = str(uuid.uuid4())
    safe_name = Path(filename).name
    dest_path = Path(settings.UPLOAD_DIR) / f"{contract_id}_{safe_name}"
    dest_path.write_bytes(file_bytes)

    parsed = process_pdf_bytes(file_bytes, filename=safe_name)
    raw_text = parsed["raw_text"]
    sections = parsed["sections"]

    rag_engine.index_contract(contract_id, sections)

    inferred_title = title.strip() if title and title.strip() else Path(safe_name).stem.replace("_", " ").title()
    contract = Contract(
        id=contract_id,
        title=inferred_title,
        original_filename=safe_name,
        file_path=dest_path.as_posix(),
        status="uploaded",
        raw_text=raw_text,
        playbook_name=playbook_name or "Standard Corporate Playbook",
        extracted_sections=sections,
    )
    db.add(contract)
    await db.commit()
    await db.refresh(contract)

    if auto_analyze:
        contract = await run_contract_analysis(db, contract)

    return contract


@router.post("/demo/{sample_type}", response_model=ContractDetail, status_code=status.HTTP_201_CREATED)
async def load_demo_contract(
    sample_type: str,
    db: AsyncSession = Depends(get_db),
) -> Contract:
    """Instant load and auto-analysis of a benchmark demo contract."""
    key = sample_type.strip().lower()
    if key not in DEMO_CONTRACTS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown demo sample '{sample_type}'. Available: {', '.join(DEMO_CONTRACTS.keys())}",
        )

    demo = DEMO_CONTRACTS[key]
    contract_id = str(uuid.uuid4())
    parsed = process_text_document(demo["text"])
    rag_engine.index_contract(contract_id, parsed["sections"])

    contract = Contract(
        id=contract_id,
        title=demo["title"],
        original_filename=demo["filename"],
        file_path=f"demo://{key}/{demo['filename']}",
        status="uploaded",
        raw_text=parsed["raw_text"],
        playbook_name=demo["playbook"],
        extracted_sections=parsed["sections"],
    )
    db.add(contract)
    await db.commit()
    await db.refresh(contract)

    contract = await run_contract_analysis(db, contract)
    return contract


@router.get("", response_model=List[ContractListItem])
@router.get("/", response_model=List[ContractListItem], include_in_schema=False)
async def list_contracts(db: AsyncSession = Depends(get_db)) -> List[Contract]:
    """List all contracts ordered by created_at DESC."""
    res = await db.execute(select(Contract).order_by(desc(Contract.created_at)))
    return list(res.scalars().all())


@router.get("/{contract_id}", response_model=ContractDetail)
async def get_contract(contract_id: str, db: AsyncSession = Depends(get_db)) -> Contract:
    """Retrieve detailed contract state including risks, transcript, redlines, and obligations."""
    res = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = res.scalar_one_or_none()
    if contract is None:
        raise HTTPException(status_code=404, detail="Contract not found.")
    return contract


@router.delete("/{contract_id}", status_code=status.HTTP_200_OK)
async def delete_contract(contract_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Delete contract row, associated audit logs, and purge ChromaDB collection."""
    res = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = res.scalar_one_or_none()
    if contract is None:
        raise HTTPException(status_code=404, detail="Contract not found.")

    # Purge ChromaDB / in-memory RAG collection
    rag_engine.delete_contract_index(contract_id)

    # Remove uploaded file on disk if present
    if contract.file_path and not contract.file_path.startswith("demo://"):
        try:
            Path(contract.file_path).unlink(missing_ok=True)
        except Exception:
            pass

    await db.execute(delete(AuditLog).where(AuditLog.contract_id == contract_id))
    await db.execute(delete(Contract).where(Contract.id == contract_id))
    await db.commit()

    return {"status": "deleted", "contract_id": contract_id, "rag_purged": True}
