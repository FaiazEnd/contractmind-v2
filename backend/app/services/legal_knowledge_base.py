"""Curated External Legal Clause & Precedent Dataset (CUAD-style risk clauses + market-standard fallbacks)."""

from __future__ import annotations

from typing import Any


LEGAL_PRECEDENT_DATASET: list[dict[str, Any]] = [
    {
        "id": "cuad-indemnity-01",
        "category": "Uncapped Indemnification",
        "source": "CUAD / ABA Model MSA Precedent",
        "risk_pattern": "Unlimited or uncapped indemnification exposes a party to unbounded balance-sheet liability exceeding contract value.",
        "market_standard_fallback": "Each party's aggregate indemnification liability shall not exceed 1x to 2x the total fees paid or payable in the twelve (12) months preceding the claim, conditioned on prompt written notice and defense control.",
        "guidance": "Always pair indemnification with a monetary super-cap and mutual reciprocity for third-party IP and bodily injury claims.",
    },
    {
        "id": "cuad-consequential-02",
        "category": "Consequential Damages Waiver",
        "source": "CUAD / Enterprise SaaS Benchmark",
        "risk_pattern": "Absence of a consequential damages waiver allows recovery of speculative lost profits, business interruption, and reputational harm.",
        "market_standard_fallback": "Neither party shall be liable for any indirect, incidental, special, consequential, or punitive damages, or loss of profits or revenue, even if advised of the possibility of such damages.",
        "guidance": "Carve-outs should be narrowly limited to confidentiality breaches, IP infringement, or willful misconduct.",
    },
    {
        "id": "cuad-ai-training-03",
        "category": "AI & Proprietary Data Rights",
        "source": "Enterprise AI Governance Standard (2025-2026)",
        "risk_pattern": "Broad licenses allowing vendors to train AI/ML foundation models on customer inputs leak trade secrets and violate enterprise data isolation.",
        "market_standard_fallback": "Vendor shall process Customer Data strictly to deliver the Services and shall not use Customer Data, prompts, or outputs to train, fine-tune, or improve any AI or machine learning models.",
        "guidance": "Require zero-retention or tenant-isolated inference guarantees for sensitive commercial and regulated data.",
    },
    {
        "id": "cuad-autorenewal-04",
        "category": "Auto-Renewal & Notice Window",
        "source": "CUAD / Commercial Procurement Precedent",
        "risk_pattern": "Silent auto-renewal clauses with 90-120 day advance notice traps lock buyers into unwanted multi-year commitments.",
        "market_standard_fallback": "Following the Initial Term, this Agreement shall renew only upon mutual written agreement, or with a 30-day non-renewal notice window preceded by a 60-day written reminder.",
        "guidance": "Replace 90+ day opt-out windows with 30-day notice or explicit opt-in renewal.",
    },
    {
        "id": "cuad-termination-cure-05",
        "category": "Termination & Cure Period",
        "source": "CUAD / Master Services Precedent",
        "risk_pattern": "Immediate termination without a cure window creates severe operational continuity risk for mission-critical software.",
        "market_standard_fallback": "Either party may terminate for material breach only if the breaching party fails to cure such breach within thirty (30) days after receiving written notice specifying the breach.",
        "guidance": "Ensure a minimum 30-day cure period for remediable breaches and pro-rata refund of prepaid unearned fees.",
    },
    {
        "id": "cuad-audit-rights-06",
        "category": "Security & Financial Audit Rights",
        "source": "SOC 2 / ISO 27001 Commercial Standard",
        "risk_pattern": "Unlimited or unannounced on-site audit rights disrupt operations and expose multi-tenant environments.",
        "market_standard_fallback": "Audits may be conducted no more than once per twelve (12) months upon thirty (30) days advance written notice during normal business hours, satisfied first via current SOC 2 Type II or ISO 27001 reports.",
        "guidance": "Default to third-party attestation reports before permitting on-site inspections.",
    },
    {
        "id": "cuad-noncompete-07",
        "category": "Non-Compete & Exclusivity",
        "source": "CUAD / Antitrust & Restraint Precedent",
        "risk_pattern": "Worldwide exclusivity or multi-year non-competes restrict procurement flexibility and risk antitrust unenforceability.",
        "market_standard_fallback": "Nothing in this Agreement creates an exclusive relationship or restricts either party from procuring or offering competing products or services, subject to strict confidentiality obligations.",
        "guidance": "If exclusivity is commercially required, narrow it to named deliverables, a defined territory, and <= 12 months.",
    },
    {
        "id": "cuad-subprocessor-08",
        "category": "Subprocessor & GDPR Governance",
        "source": "GDPR Art. 28 / Standard Contractual Clauses",
        "risk_pattern": "Unrestricted subprocessor delegation without notice or liability shield violates GDPR Art. 28 accountability.",
        "market_standard_fallback": "Processor shall provide thirty (30) days prior written notice before engaging any new subprocessor, permit reasonable objection, and remain fully liable for all subprocessor acts and omissions.",
        "guidance": "Flow down equivalent data protection obligations to every subprocessor.",
    },
    {
        "id": "cuad-liquidated-09",
        "category": "Liquidated Damages & Penalties",
        "source": "CUAD / Common Law Remedy Precedent",
        "risk_pattern": "Punitive liquidated damages (e.g., 200% of remaining fees) are unenforceable penalties and distort exit economics.",
        "market_standard_fallback": "Any pre-agreed remedies or SLA service credits shall be proportional to demonstrable direct loss and shall not constitute a penalty or require forfeiture of unearned prepaid fees.",
        "guidance": "Tie early-termination remedies to actual unrecovered wind-down costs rather than multipliers.",
    },
    {
        "id": "cuad-governing-law-10",
        "category": "Governing Law & Order of Precedence",
        "source": "EDGAR Multi-Document Deal Room Precedent",
        "risk_pattern": "Conflicting governing law clauses across MSA, SOW, and DPA trigger parallel litigation and forum-shopping.",
        "market_standard_fallback": "All Deal Documents shall be governed by a single agreed jurisdiction (e.g., Delaware or New York), with an explicit Order of Precedence: (1) DPA for data protection, (2) MSA, (3) SOWs for scope/pricing.",
        "guidance": "Harmonize venue and precedence across all interrelated agreements before execution.",
    },
]
