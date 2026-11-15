"""Async SQLAlchemy 2.0 database engine, session management, and playbook seeding."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


DEFAULT_PLAYBOOKS = [
    {
        "name": "Standard Corporate Playbook",
        "description": "Balanced enterprise risk standards covering liability caps, indemnification, AI data protection, cure windows, and governing law.",
        "is_default": True,
        "rules": [
            {
                "id": "rule-indemnity",
                "category": "Indemnification Cap",
                "standard_requirement": "Mutual indemnification capped at 12 months of fees paid or payable.",
                "unacceptable_terms": ["unlimited", "uncapped", "without limitation", "indemnify against all claims"],
                "preferred_fallback": "Each party's aggregate indemnification liability shall not exceed the total fees paid or payable under this Agreement in the twelve (12) months preceding the claim.",
                "severity_if_missing": "CRITICAL",
            },
            {
                "id": "rule-consequential",
                "category": "Consequential Damages Waiver",
                "standard_requirement": "Mutual waiver of indirect, consequential, incidental, and lost-profit damages.",
                "unacceptable_terms": ["liable for consequential", "including lost profits", "all indirect damages"],
                "preferred_fallback": "Neither party shall be liable for any indirect, incidental, special, consequential, or punitive damages, or any loss of profits or revenue.",
                "severity_if_missing": "HIGH",
            },
            {
                "id": "rule-ai-training",
                "category": "AI & Proprietary Data Rights",
                "standard_requirement": "Strict prohibition on using Customer Data or Confidential Information to train machine learning or AI models.",
                "unacceptable_terms": ["train machine learning", "train ai models", "improve artificial intelligence", "perpetual license to customer data"],
                "preferred_fallback": "Vendor shall not use Customer Data, inputs, or outputs to train, fine-tune, or improve any foundation or machine learning models.",
                "severity_if_missing": "CRITICAL",
            },
            {
                "id": "rule-termination-cure",
                "category": "Termination Cure Period",
                "standard_requirement": "Minimum 30-day written notice and cure period prior to termination for material breach.",
                "unacceptable_terms": ["terminate immediately without notice", "without cure period", "immediate termination upon any breach"],
                "preferred_fallback": "Either party may terminate for material breach if such breach remains uncured thirty (30) days after receipt of written notice specifying the breach.",
                "severity_if_missing": "HIGH",
            },
            {
                "id": "rule-autorenewal",
                "category": "Renewal & Notice Window",
                "standard_requirement": "Opt-in renewal or minimum 30-day notice window with reminder prior to auto-renewal.",
                "unacceptable_terms": ["automatically renew", "90 days prior", "120 days prior", "irrevocably renew"],
                "preferred_fallback": "This Agreement shall renew only upon mutual written consent, or upon thirty (30) days prior written notice of non-renewal.",
                "severity_if_missing": "MEDIUM",
            },
            {
                "id": "rule-audit-rights",
                "category": "Security & Financial Audit Rights",
                "standard_requirement": "Audits limited to once annually upon 30 days written notice during normal business hours.",
                "unacceptable_terms": ["audit at any time", "unannounced audit", "unlimited audit rights", "at vendor's sole expense"],
                "preferred_fallback": "Audits may occur no more than once per twelve (12) months upon thirty (30) days advance written notice during normal business hours.",
                "severity_if_missing": "MEDIUM",
            },
        ],
    },
    {
        "name": "Enterprise SaaS Vendor Playbook",
        "description": "Cloud & SaaS compliance standards emphasizing GDPR/DPA subprocessor controls, SOC2 obligations, and SLA service credits.",
        "is_default": False,
        "rules": [
            {
                "id": "saas-ai-data",
                "category": "AI & Proprietary Data Rights",
                "standard_requirement": "Zero retention or model training on tenant data.",
                "unacceptable_terms": ["train ai", "machine learning models", "aggregate and commercialize"],
                "preferred_fallback": "Provider processes Customer Data solely to deliver the SaaS Services and never for AI model training.",
                "severity_if_missing": "CRITICAL",
            },
            {
                "id": "saas-subprocessors",
                "category": "Subprocessor Governance",
                "standard_requirement": "30-day advance notice of new subprocessors with right to object.",
                "unacceptable_terms": ["any third party without notice", "unrestricted subprocessor", "no liability for subprocessors"],
                "preferred_fallback": "Processor shall provide thirty (30) days prior written notice before engaging any new subprocessor and remains fully liable for subprocessor performance.",
                "severity_if_missing": "HIGH",
            },
            {
                "id": "saas-liability",
                "category": "Indemnification Cap",
                "standard_requirement": "Liability cap aligned at 12-24 months fees with super-cap for data breach.",
                "unacceptable_terms": ["unlimited liability", "uncapped indemnification"],
                "preferred_fallback": "Aggregate liability shall be capped at 2x annual subscription fees for data protection breaches and 1x annual fees otherwise.",
                "severity_if_missing": "CRITICAL",
            },
        ],
    },
    {
        "name": "Strict M&A & IP Playbook",
        "description": "High-scrutiny M&A, Joint IP, and Strategic Acquisition guidelines protecting background IP, exclusivity, and fee shifting.",
        "is_default": False,
        "rules": [
            {
                "id": "ma-noncompete",
                "category": "Exclusivity & Non-Compete",
                "standard_requirement": "Narrowly tailored scope limited to specific competing products and <= 12 months.",
                "unacceptable_terms": ["perpetual non-compete", "worldwide exclusivity", "any competing business for five years"],
                "preferred_fallback": "Any restrictive covenant shall be limited to directly competing deliverables within the defined territory for twelve (12) months.",
                "severity_if_missing": "HIGH",
            },
            {
                "id": "ma-fees",
                "category": "Attorney Fee Shifting",
                "standard_requirement": "Prevailing-party mutual fee recovery or each party bears own legal costs.",
                "unacceptable_terms": ["solely reimburse", "regardless of outcome", "one-way attorney fees"],
                "preferred_fallback": "In any action to enforce this Agreement, the prevailing party shall be entitled to recover reasonable attorneys' fees and costs.",
                "severity_if_missing": "MEDIUM",
            },
            {
                "id": "ma-liquidated",
                "category": "Liquidated Damages",
                "standard_requirement": "Proportional pre-agreed remedies tied to demonstrable actual loss, never punitive penalties.",
                "unacceptable_terms": ["penalty of", "liquidated damages of 200%", "forfeiture of all fees"],
                "preferred_fallback": "Any service credits or pre-agreed remedies represent a reasonable pre-estimate of loss and not a penalty.",
                "severity_if_missing": "HIGH",
            },
        ],
    },
]


_db_lock = asyncio.Lock()
_db_initialized = False


async def ensure_db_initialized() -> None:
    """Idempotently initialize schema and seed playbooks (safe for serverless cold starts)."""
    global _db_initialized
    if _db_initialized:
        return
    async with _db_lock:
        if _db_initialized:
            return
        await init_db()
        _db_initialized = True


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async SQLAlchemy session."""
    await ensure_db_initialized()
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create tables and seed default corporate playbooks if absent."""
    # Ensure models are imported before create_all
    from app.models import audit, contract, user  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        existing = await session.execute(select(contract.Playbook))
        if not existing.scalars().first():
            for pb in DEFAULT_PLAYBOOKS:
                session.add(
                    contract.Playbook(
                        name=pb["name"],
                        description=pb["description"],
                        rules=pb["rules"],
                        is_default=pb["is_default"],
                    )
                )
            await session.commit()
