"""Async SQLAlchemy 2.0 engine, session management, and database initialization."""
from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False}
    if settings.DATABASE_URL.startswith("sqlite")
    else {},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


DEFAULT_PLAYBOOKS = [
    {
        "name": "Standard Corporate Playbook",
        "description": "Balanced enterprise risk posture covering liability caps, mutual indemnification, data privacy, cure periods, and termination fairness.",
        "is_default": True,
        "rules": [
            {
                "category": "Limitation of Liability",
                "standard_requirement": "Mutual liability cap equal to 12 months of fees paid or payable, with mutual exclusion of consequential, indirect, and punitive damages.",
                "unacceptable_terms": ["unlimited liability", "uncapped", "no limitation", "consequential damages excluded only for vendor"],
                "preferred_fallback": "Aggregate liability of either party shall not exceed the total fees paid or payable under this Agreement during the twelve (12) months preceding the claim, and neither party shall be liable for indirect or consequential damages.",
                "severity_if_missing": "CRITICAL",
            },
            {
                "category": "Indemnification",
                "standard_requirement": "Mutual third-party IP and gross negligence indemnification subject to the negotiated liability cap or super-cap (2x fees).",
                "unacceptable_terms": ["indemnify without limitation", "uncapped indemnification", "all claims arising from any use"],
                "preferred_fallback": "Indemnifying Party shall defend and indemnify Indemnified Party against third-party claims up to two times (2x) annual contract fees, conditioned on prompt written notice and sole control of defense.",
                "severity_if_missing": "CRITICAL",
            },
            {
                "category": "AI & Proprietary Data Rights",
                "standard_requirement": "Strict prohibition on training foundational or third-party AI/ML models on Customer Confidential Information or proprietary inputs.",
                "unacceptable_terms": ["train artificial intelligence", "machine learning models", "improve our models", "perpetual license to customer data"],
                "preferred_fallback": "Provider shall not use, retain, or process Customer Data to train, fine-tune, or improve generalized artificial intelligence or machine learning models.",
                "severity_if_missing": "CRITICAL",
            },
            {
                "category": "Termination & Cure Period",
                "standard_requirement": "Minimum 30-day written notice and opportunity to cure material breaches before termination for cause.",
                "unacceptable_terms": ["terminate immediately without notice", "without cure period", "at sole discretion immediately"],
                "preferred_fallback": "Either party may terminate for material breach if such breach remains uncured thirty (30) days after receipt of detailed written notice.",
                "severity_if_missing": "HIGH",
            },
            {
                "category": "Auto-Renewal & Notice",
                "standard_requirement": "Opt-in renewal or at least 60-day advance written reminder window prior to auto-renewal lock-in.",
                "unacceptable_terms": ["automatically renew unless", "without prior notice", "90 days prior notice"],
                "preferred_fallback": "Renewal shall require mutual written confirmation or at least thirty (30) days prior written notice following a mandatory 60-day vendor renewal reminder.",
                "severity_if_missing": "MEDIUM",
            },
            {
                "category": "Audit Rights",
                "standard_requirement": "Annual audits capped at once per 12 months with 30 days advance notice during business hours, satisfied via SOC 2 Type II report.",
                "unacceptable_terms": ["audit at any time", "unlimited audit", "without prior notice", "at customer's sole expense"],
                "preferred_fallback": "Audits may occur no more than once annually upon thirty (30) days written notice during regular business hours, and may be satisfied by delivery of an independent SOC 2 Type II report.",
                "severity_if_missing": "MEDIUM",
            },
        ],
    },
    {
        "name": "Strict M&A & IP Playbook",
        "description": "High-protection M&A and Intellectual Property acquisition standards guarding against uncapped escrow exposure, IP contamination, and non-compete overbreadth.",
        "is_default": False,
        "rules": [
            {
                "category": "Indemnification Escrow & Cap",
                "standard_requirement": "Indemnification obligations strictly capped at escrow holdback (10-15% of purchase price) except for fraud.",
                "unacceptable_terms": ["uncapped indemnification", "unlimited personal liability", "indemnify without cap"],
                "preferred_fallback": "Seller's aggregate indemnification liability shall be capped at fifteen percent (15%) of the Purchase Price held in Escrow, except in cases of proven intentional fraud.",
                "severity_if_missing": "CRITICAL",
            },
            {
                "category": "IP Ownership & Open Source",
                "standard_requirement": "Clean chain of title warranties with bounded remediation and no copyleft viral contamination.",
                "unacceptable_terms": ["as-is without warranty", "no representation regarding ip", "background ip transfers"],
                "preferred_fallback": "Seller warrants valid ownership of Transferred IP free of liens, with Pre-Existing Background IP retained by Seller under a non-exclusive perpetual license solely as embedded.",
                "severity_if_missing": "CRITICAL",
            },
            {
                "category": "Non-Compete Scope",
                "standard_requirement": "Restrictive covenants reasonably tailored in duration (<= 24 months), geography, and competing product lines.",
                "unacceptable_terms": ["perpetual non-compete", "worldwide exclusivity", "any business whatsoever"],
                "preferred_fallback": "Non-competition covenants shall remain in force for twenty-four (24) months post-Closing solely within directly competing enterprise product categories.",
                "severity_if_missing": "HIGH",
            },
            {
                "category": "Attorney Fee Shifting",
                "standard_requirement": "Prevailing party mutual fee recovery or each party bears its own legal fees.",
                "unacceptable_terms": ["only buyer recovers", "vendor shall be entitled to all legal fees"],
                "preferred_fallback": "In any dispute arising hereunder, the prevailing party as determined by final judgment shall be entitled to recover reasonable outside attorneys' fees.",
                "severity_if_missing": "MEDIUM",
            },
        ],
    },
    {
        "name": "Cloud & GDPR Privacy Playbook",
        "description": "Privacy-first cloud & DPA review standard enforcing subprocessor consent, 48-hour breach notification, zero AI training, and verified deletion.",
        "is_default": False,
        "rules": [
            {
                "category": "AI & Telemetry Restriction",
                "standard_requirement": "Zero training of AI/LLM models on Personal Data or Tenant Content.",
                "unacceptable_terms": ["train models", "aggregated insights without consent", "ai training"],
                "preferred_fallback": "Processor shall never use Personal Data or Customer Content to train, validate, or tune artificial intelligence models.",
                "severity_if_missing": "CRITICAL",
            },
            {
                "category": "Subprocessor Governance",
                "standard_requirement": "30-day prior written notice and right to object before onboarding new subprocessors, with full flow-down liability.",
                "unacceptable_terms": ["subprocessors without notice", "not liable for subprocessors", "shielded from subprocessor"],
                "preferred_fallback": "Processor shall provide thirty (30) days advance written notice of any new subprocessor, grant Customer an objection right, and remain fully liable for subprocessor performance.",
                "severity_if_missing": "HIGH",
            },
            {
                "category": "Data Deletion & Return",
                "standard_requirement": "Certified deletion or return of all Customer Data within 30 days of contract termination.",
                "unacceptable_terms": ["retain indefinitely", "no obligation to delete"],
                "preferred_fallback": "Within thirty (30) days following termination, Processor shall securely return or cryptographically destroy all Personal Data and provide written certification.",
                "severity_if_missing": "HIGH",
            },
            {
                "category": "Liquidated Damages & Penalties",
                "standard_requirement": "Proportionate SLA service credits rather than punitive liquidated damages multipliers.",
                "unacceptable_terms": ["liquidated damages", "10x penalty", "punitive fee"],
                "preferred_fallback": "Exclusive remedy for SLA downtime shall be capped service credits up to fifteen percent (15%) of monthly subscription fees.",
                "severity_if_missing": "HIGH",
            },
        ],
    },
]


async def init_db() -> None:
    """Create database tables and seed default playbooks."""
    from app.models.audit import AuditLog  # noqa: F401
    from app.models.contract import Contract, Playbook  # noqa: F401
    from app.models.user import User  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        existing = await session.execute(select(Playbook))
        if not existing.scalars().first():
            for pb in DEFAULT_PLAYBOOKS:
                session.add(Playbook(**pb))
            await session.commit()
