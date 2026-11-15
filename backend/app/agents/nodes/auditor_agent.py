"""Auditor Agent Node: scans contract sections against 10 enterprise risk categories."""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.agents.llm_client import llm_gateway
from app.agents.state import ContractAgentState

RISK_CATALOG: List[Dict[str, Any]] = [
    {
        "category": "Uncapped Indemnification",
        "severity": "CRITICAL",
        "score": 90,
        "pattern": re.compile(
            r"(?:indemnify|hold harmless).*?(?:unlimited|without limitation|uncapped|any and all claims whatsoever|no cap)",
            re.IGNORECASE | re.DOTALL,
        ),
        "rationale": "Exposes the enterprise to unbounded third-party and direct indemnification liabilities without a monetary ceiling or defense-control safeguards.",
        "mitigation": "Subject indemnification to an aggregate super-cap equal to 2x annual fees, conditioned on prompt written notice and sole defense control.",
        "consensus_template": (
            "Each party shall indemnify, defend, and hold harmless the other party from third-party claims arising out of "
            "bodily injury, tangible property damage, or third-party IP infringement, provided that: (a) the indemnified party "
            "gives prompt written notice and sole control of defense, and (b) each party's aggregate indemnification liability "
            "shall not exceed two times (2x) the total fees paid or payable in the preceding twelve (12) months."
        ),
    },
    {
        "category": "Consequential Damages Waiver Missing",
        "severity": "HIGH",
        "score": 75,
        "pattern": re.compile(
            r"(?:liable for.*?(?:indirect|consequential|incidental|special|lost profits)|excludes? no consequential damages|notwithstanding.*?consequential)",
            re.IGNORECASE | re.DOTALL,
        ),
        "rationale": "Lacks a mutual exclusion for indirect, consequential, or lost-profit damages, amplifying financial exposure from operational disputes.",
        "mitigation": "Insert a mutual consequential damages waiver with standard carve-outs only for willful misconduct and confidentiality breaches.",
        "consensus_template": (
            "IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, "
            "OR LOSS OF PROFITS OR REVENUE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGES. EACH PARTY'S AGGREGATE CUMULATIVE "
            "LIABILITY UNDER THIS AGREEMENT SHALL NOT EXCEED THE FEES PAID OR PAYABLE IN THE TWELVE (12) MONTHS PRECEDING THE CLAIM."
        ),
    },
    {
        "category": "AI Model Training on Proprietary Data",
        "severity": "CRITICAL",
        "score": 95,
        "pattern": re.compile(
            r"(?:train(?:ing)?\s+(?:its\s+)?(?:ai|artificial intelligence|machine learning|foundation|llm)\s+models?|improve.*?(?:ai|machine learning)\s+algorithms?|perpetual.*?(?:license|right).*?customer data)",
            re.IGNORECASE | re.DOTALL,
        ),
        "rationale": "Grants vendor broad rights to ingest confidential customer inputs and outputs into shared AI/ML training pipelines, risking IP leakage.",
        "mitigation": "Explicitly prohibit training or fine-tuning shared AI models on Customer Data and mandate tenant isolation.",
        "consensus_template": (
            "Customer retains all right, title, and interest in and to Customer Data, prompts, and outputs. Provider shall NOT "
            "use, retain, or process Customer Data to train, fine-tune, or improve any foundation models, artificial intelligence "
            "systems, or machine learning weights shared across customers. Processing is strictly limited to delivering the Services."
        ),
    },
    {
        "category": "Auto-Renewal Without Notice Trap",
        "severity": "MEDIUM",
        "score": 55,
        "pattern": re.compile(
            r"(?:automatically renew|auto-renew).*?(?:90\s*days|120\s*days|successive\s+(?:two|three|3)\s+year|irrevocably|without\s+(?:prior\s+)?notice)",
            re.IGNORECASE | re.DOTALL,
        ),
        "rationale": "Locks the enterprise into multi-year auto-renewals with punitive or silent non-renewal notice deadlines.",
        "mitigation": "Limit renewals to 1-year terms with a 30-day non-renewal opt-out window and mandatory 45-day vendor reminder.",
        "consensus_template": (
            "Following the Initial Term, this Agreement shall renew for successive one (1) year periods unless either party "
            "delivers written notice of non-renewal at least thirty (30) days prior to expiration. Provider shall send an "
            "automated written renewal reminder at least forty-five (45) days before the non-renewal deadline."
        ),
    },
    {
        "category": "Immediate Termination Without Cure Window",
        "severity": "HIGH",
        "score": 70,
        "pattern": re.compile(
            r"(?:terminate\s+immediately\s+without|without\s+(?:prior\s+)?notice\s+or\s+(?:opportunity\s+to\s+)?cure|no\s+cure\s+period|sole\s+discretion\s+immediately)",
            re.IGNORECASE | re.DOTALL,
        ),
        "rationale": "Permits unilateral abrupt termination without written breach notice or a fair cure period, threatening business continuity.",
        "mitigation": "Require written notice specifying the alleged breach and a minimum 30-day cure period prior to termination.",
        "consensus_template": (
            "Either party may terminate this Agreement for material breach only upon thirty (30) days' prior written notice "
            "detailing the breach in reasonable specificity, provided such breach remains uncured at the expiration of the "
            "thirty (30) day cure period."
        ),
    },
    {
        "category": "Unlimited Audit Rights",
        "severity": "MEDIUM",
        "score": 50,
        "pattern": re.compile(
            r"(?:audit\s+at\s+any\s+time|unannounced\s+(?:on-site\s+)?audit|unlimited\s+audit|audit.*?without\s+(?:prior\s+)?notice|at\s+customer'?s\s+sole\s+expense)",
            re.IGNORECASE | re.DOTALL,
        ),
        "rationale": "Exposes operations to disruptive unannounced audits at arbitrary frequency and shifted costs.",
        "mitigation": "Restrict audits to once annually with 30 days written notice, business-hours scope, and reliance on SOC 2 Type II reports.",
        "consensus_template": (
            "Not more than once per calendar year, upon thirty (30) days' prior written notice and subject to standard "
            "confidentiality obligations, Provider may satisfy audit requirements by delivering current SOC 2 Type II or "
            "ISO 27001 attestation reports, with on-site inspection permitted during normal business hours only if material gaps remain."
        ),
    },
    {
        "category": "Asymmetric Attorney Fee Shifting",
        "severity": "MEDIUM",
        "score": 45,
        "pattern": re.compile(
            r"(?:customer\s+shall\s+reimburse.*?attorneys?'?\s+fees|vendor\s+shall\s+be\s+entitled\s+to\s+recover.*?(?:attorneys?'?\s+fees|collection\s+costs)|unilateral.*?legal\s+fees)",
            re.IGNORECASE | re.DOTALL,
        ),
        "rationale": "One-way fee shifting deters legitimate customer enforcement while subsidizing vendor litigation.",
        "mitigation": "Replace with standard mutual prevailing-party attorney fee recovery or American Rule allocation.",
        "consensus_template": (
            "In any formal legal action or arbitration brought to enforce this Agreement, the prevailing party as determined by "
            "a court or tribunal of competent jurisdiction shall be entitled to recover its reasonable documented attorneys' fees and costs."
        ),
    },
    {
        "category": "Non-Compete / Exclusivity Overbreadth",
        "severity": "HIGH",
        "score": 80,
        "pattern": re.compile(
            r"(?:exclusive\s+provider|shall\s+not\s+(?:engage|procure|develop|use).*?(?:competing|similar)\s+(?:services|software|products)|worldwide\s+non-compete|exclusivity)",
            re.IGNORECASE | re.DOTALL,
        ),
        "rationale": "Imposes sweeping non-compete or vendor exclusivity restrictions that block multi-vendor resilience and internal R&D.",
        "mitigation": "Delete exclusivity/non-compete covenants and affirm non-exclusive commercial relationship.",
        "consensus_template": (
            "This Agreement is non-exclusive. Nothing herein restricts Customer or its affiliates from procuring, developing, "
            "or using competing or similar products or services from any third party, nor restricts Provider from serving other customers "
            "subject to strict confidentiality obligations."
        ),
    },
    {
        "category": "Broad Data Exfiltration / Subprocessor Shield",
        "severity": "HIGH",
        "score": 75,
        "pattern": re.compile(
            r"(?:subprocessors?\s+without\s+(?:prior\s+)?notice|disclaims?\s+all\s+liability\s+for\s+(?:third-party\s+)?subprocessors?|transfer\s+customer\s+data.*?without\s+consent)",
            re.IGNORECASE | re.DOTALL,
        ),
        "rationale": "Allows silent subprocessor onboarding while disclaiming flow-down security and privacy accountability.",
        "mitigation": "Require 30-day advance subprocessor notice, objection rights, and full vendor liability for subprocessor acts.",
        "consensus_template": (
            "Provider shall remain fully liable for the acts and omissions of all subprocessors to the same extent as its own. "
            "Provider shall maintain an up-to-date subprocessor list and provide thirty (30) days' prior written notice of any "
            "new subprocessor, during which Customer may object on reasonable data-protection grounds."
        ),
    },
    {
        "category": "Liquidated Damages Penalty Trap",
        "severity": "HIGH",
        "score": 70,
        "pattern": re.compile(
            r"(?:liquidated\s+damages.*?(?:100%|remaining\s+term|acceleration|penalty)|early\s+termination\s+fee\s+equal\s+to\s+100%|minimum\s+penalty\s+of)",
            re.IGNORECASE | re.DOTALL,
        ),
        "rationale": "Enforces disproportionate fee acceleration or punitive liquidated damages even upon vendor breach or lawful termination.",
        "mitigation": "Eliminate punitive acceleration upon termination for cause and restrict remedies to pro-rata earned fees.",
        "consensus_template": (
            "Upon termination by Customer for Provider's uncured material breach, Customer shall have no liability for remaining "
            "unearned fees and Provider shall promptly refund all prepaid, unused fees on a pro-rata basis from the effective "
            "date of termination."
        ),
    },
]


async def auditor_node(state: ContractAgentState) -> ContractAgentState:
    """Scan extracted sections against the 10 risk categories and record Auditor arguments."""
    t0 = time.time()
    sections: List[Dict[str, Any]] = list(state.get("sections") or [])
    identified_risks: List[Dict[str, Any]] = list(state.get("identified_risks") or [])
    transcript: List[Dict[str, Any]] = list(state.get("debate_transcript") or [])
    audit_events: List[Dict[str, Any]] = list(state.get("audit_events") or [])

    matched_categories = set()
    for sec in sections:
        sec_num = str(sec.get("section_number", "1"))
        sec_title = str(sec.get("title", f"Section {sec_num}"))
        sec_text = str(sec.get("text", ""))

        for spec in RISK_CATALOG:
            if spec["category"] in matched_categories:
                continue
            if spec["pattern"].search(sec_text):
                matched_categories.add(spec["category"])
                risk_id = f"risk-{len(identified_risks) + 1}"
                excerpt = sec_text[:450].strip()
                risk_obj = {
                    "id": risk_id,
                    "category": spec["category"],
                    "severity": spec["severity"],
                    "score": float(spec["score"]),
                    "section_number": sec_num,
                    "section_title": sec_title,
                    "matched_excerpt": excerpt,
                    "original_text": sec_text,
                    "legal_rationale": spec["rationale"],
                    "suggested_mitigation": spec["mitigation"],
                    "consensus_template": spec["consensus_template"],
                }
                identified_risks.append(risk_obj)

                transcript.append(
                    {
                        "turn_index": len(transcript) + 1,
                        "agent_name": "Auditor Agent",
                        "role": "Enterprise Compliance Defender",
                        "section_number": sec_num,
                        "risk_category": spec["category"],
                        "argument": (
                            f"[{spec['severity']} | Score {spec['score']}] Flagged in Section {sec_num} ({sec_title}): "
                            f"{spec['rationale']} Recommended guardrail: {spec['mitigation']}"
                        ),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )

    # Optional LLM synthesis summary for telemetry + enrichment
    llm_res = await llm_gateway.generate(
        prompt=(
            f"Summarize the top {len(identified_risks)} enterprise risks found in '{state.get('title', 'Agreement')}': "
            + ", ".join(r["category"] for r in identified_risks)
        ),
        system_instruction="You are the Auditor Agent (Enterprise Defender). Be concise and authoritative.",
        fallback_text=(
            f"Auditor Agent completed scan across {len(sections)} sections and flagged "
            f"{len(identified_risks)} material risk vectors."
        ),
    )

    latency_ms = round((time.time() - t0) * 1000.0, 2)
    audit_events.append(
        {
            "agent_name": "Auditor Agent",
            "action": "risk_scan_and_audit",
            "model_name": llm_res.model_name,
            "prompt_tokens": llm_res.prompt_tokens,
            "completion_tokens": llm_res.completion_tokens,
            "total_tokens": llm_res.total_tokens,
            "latency_ms": max(latency_ms, llm_res.latency_ms),
            "estimated_cost_usd": llm_res.estimated_cost_usd,
        }
    )

    state["identified_risks"] = identified_risks
    state["debate_transcript"] = transcript
    state["audit_events"] = audit_events
    return state
