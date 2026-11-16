"""Contracts ingestion, demo benchmark loader, listing, retrieval, and deletion endpoints."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_contract_or_404
from app.config import settings
from app.database import get_db
from app.models.audit import AuditLog
from app.models.contract import Contract
from app.schemas.contract_schemas import (
    ContractDetailResponse,
    ContractSummaryResponse,
)
from app.services.orchestrator import run_contract_analysis
from app.services.pdf_processor import process_document_bytes, process_raw_text
from app.services.rag_engine import rag_engine
from app.services.sample_contracts import SAMPLE_CONTRACTS

router = APIRouter(prefix="/contracts", tags=["contracts"])


def _to_summary(c: Contract) -> ContractSummaryResponse:
    return ContractSummaryResponse(
        id=c.id,
        title=c.title,
        original_filename=c.original_filename,
        status=c.status,
        playbook_name=c.playbook_name,
        overall_risk_score=c.overall_risk_score,
        risk_summary=c.risk_summary or {"critical": 0, "high": 0, "medium": 0, "low": 0},
        redline_count=len(c.redlines or []),
        obligation_count=len(c.obligations or []),
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


def _to_detail(c: Contract) -> ContractDetailResponse:
    return ContractDetailResponse(
        id=c.id,
        title=c.title,
        original_filename=c.original_filename,
        status=c.status,
        error_message=c.error_message,
        raw_text=c.raw_text,
        playbook_name=c.playbook_name,
        overall_risk_score=c.overall_risk_score,
        extracted_sections=c.extracted_sections or [],
        identified_risks=c.identified_risks or [],
        debate_transcript=c.debate_transcript or [],
        redlines=c.redlines or [],
        obligations=c.obligations or [],
        risk_summary=c.risk_summary or {"critical": 0, "high": 0, "medium": 0, "low": 0},
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.post("/upload", response_model=ContractDetailResponse, status_code=status.HTTP_201_CREATED)
async def upload_contract(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    playbook_name: str = Form("Standard Corporate Playbook"),
    auto_analyze: bool = Form(True),
    db: AsyncSession = Depends(get_db),
) -> ContractDetailResponse:
    """Ingest PDF/DOCX/TXT contract, extract tables & sections, redact PII, index RAG, and optionally analyze."""
    filename = file.filename or "uploaded_contract.pdf"
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    contract_id = str(uuid.uuid4())
    safe_name = Path(filename).name
    dest_path = settings.UPLOAD_DIR / f"{contract_id}_{safe_name}"
    dest_path.write_bytes(file_bytes)

    parsed = process_document_bytes(file_bytes, safe_name)
    derived_title = (
        title.strip()
        if title and title.strip()
        else Path(safe_name).stem.replace("_", " ").replace("-", " ").title()
    )

    contract = Contract(
        id=contract_id,
        title=derived_title,
        original_filename=safe_name,
        file_path=str(dest_path),
        status="uploaded",
        raw_text=parsed["raw_text"],
        playbook_name=playbook_name,
        extracted_sections=parsed["sections"],
    )
    db.add(contract)
    await db.commit()
    await db.refresh(contract)

    rag_engine.index_contract(contract.id, parsed["sections"])

    if auto_analyze:
        contract = await run_contract_analysis(db, contract)

    return _to_detail(contract)


@router.post("/demo/{sample_type}", response_model=ContractDetailResponse, status_code=status.HTTP_201_CREATED)
async def load_demo_contract(
    sample_type: str,
    playbook_name: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> ContractDetailResponse:
    """Instant load and auto-analysis of one of the 6 benchmark commercial contracts."""
    key = sample_type.lower().strip()
    if key not in SAMPLE_CONTRACTS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown demo sample '{sample_type}'. Valid types: {', '.join(SAMPLE_CONTRACTS.keys())}",
        )

    tpl = SAMPLE_CONTRACTS[key]
    parsed = process_raw_text(tpl["text"])
    chosen_playbook = playbook_name or tpl["playbook_name"]

    contract = Contract(
        id=str(uuid.uuid4()),
        title=tpl["title"],
        original_filename=tpl["filename"],
        file_path="",
        status="uploaded",
        raw_text=parsed["raw_text"],
        playbook_name=chosen_playbook,
        extracted_sections=parsed["sections"],
    )
    db.add(contract)
    await db.commit()
    await db.refresh(contract)

    rag_engine.index_contract(contract.id, parsed["sections"])
    contract = await run_contract_analysis(db, contract)
    return _to_detail(contract)


@router.get("/", response_model=list[ContractSummaryResponse])
async def list_contracts(db: AsyncSession = Depends(get_db)) -> list[ContractSummaryResponse]:
    """List all ingested contracts ordered by created_at DESC."""
    res = await db.execute(select(Contract).order_by(Contract.created_at.desc()))
    contracts = res.scalars().all()
    return [_to_summary(c) for c in contracts]


@router.get("/{contract_id}", response_model=ContractDetailResponse)
async def get_contract(
    contract: Contract = Depends(get_contract_or_404),
) -> ContractDetailResponse:
    """Retrieve complete contract details, risks, debate transcript, redlines, and obligations."""
    return _to_detail(contract)


@router.delete("/{contract_id}")
async def delete_contract(
    contract_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete contract record, associated audit telemetry logs, and purge ChromaDB vector index."""
    contract = await get_contract_or_404(contract_id, db)

    if contract.file_path:
        try:
            fp = Path(contract.file_path)
            if fp.exists():
                fp.unlink()
        except Exception:
            pass

    await db.execute(delete(AuditLog).where(AuditLog.contract_id == contract_id))
    await db.delete(contract)
    await db.commit()

    rag_purged = rag_engine.delete_contract_index(contract_id)
    return {
        "deleted": True,
        "contract_id": contract_id,
        "rag_index_purged": rag_purged,
    }
