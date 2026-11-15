"""Auditor Agent Node: Enterprise defender & compliance risk scanner across 10 canonical risk categories."""

from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.agents.llm_client import llm_gateway
from app.agents.state import ContractGraphState


RISK_SIGNATURES: list[dict[str, Any]] = [
    {
        "key": "uncapped_indemnification",
        "category": "Uncapped Indemnification",
        "severity": "CRITICAL",
        "score": 90.0,
        "pattern": re.compile(
            r"(?:unlimited|uncapped|without\s+(?:any\s+)?(?:cap|limitation)|no\s+monetary\s+cap)[^.]*indemnif|indemnif[^.]*(?:unlimited|uncapped|without\s+limitation|all\s+claims\s+whatsoever)",
            re.IGNORECASE,
        ),
        "legal_rationale": "Exposes the enterprise to unbounded balance-sheet liability far exceeding contract value without a reciprocal 12-month fee cap.",
        "suggested_mitigation": "Party's aggregate indemnification obligations under this Agreement shall be capped at one times (1x) the total fees paid or payable in the twelve (12) months preceding the claim, and conditioned on prompt written notice and defense control.",
    },
    {
        "key": "consequential_damages_missing",
        "category": "Consequential Damages Waiver Missing",
        "severity": "HIGH",
        "score": 75.0,
        "pattern": re.compile(
            r"(?:liable\s+for\s+(?:all\s+)?(?:indirect|consequential|incidental|special|punitive)|including\s+lost\s+profits|no\s+waiver\s+of\s+consequential|shall\s+not\s+exclude\s+consequential)",
            re.IGNORECASE,
        ),
        "legal_rationale": "Permits recovery of speculative indirect damages and lost profits, multiplying financial exposure beyond direct contract losses.",
        "suggested_mitigation": "In no event shall either party be liable to the other for any indirect, incidental, special, consequential, or punitive damages, or loss of profits, revenue, or data, even if advised of the possibility of such damages.",
    },
    {
        "key": "ai_model_training",
        "category": "AI Model Training on Proprietary Data",
        "severity": "CRITICAL",
        "score": 95.0,
        "pattern": re.compile(
            r"(?:train\s+(?:its\s+|any\s+)?(?:proprietary\s+)?(?:ai|artificial\s+intelligence|machine\s+learning|foundation)\s+models?|use\s+customer\s+data\s+to\s+improve\s+(?:ai|models|algorithms)|perpetual\s+(?:royalty-free\s+)?license\s+to\s+(?:all\s+)?(?:inputs|customer\s+data))",
            re.IGNORECASE,
        ),
        "legal_rationale": "Transfers enterprise trade secrets, confidential prompts, and proprietary datasets into vendor foundation models without isolation guarantees.",
        "suggested_mitigation": "Vendor shall process Customer Data strictly to perform the Services and shall not use Customer Data, prompts, or outputs to train, fine-tune, or improve any artificial intelligence or machine learning models.",
    },
    {
        "key": "auto_renewal_trap",
        "category": "Auto-Renewal Without Notice Trap",
        "severity": "MEDIUM",
        "score": 55.0,
        "pattern": re.compile(
            r"(?:automatically\s+renew|auto-renew|irrevocably\s+renew)[^.]*(?:90|120|180)\s*days|automatically\s+renew\s+for\s+successive\s+(?:one|two|three|\d+)[\s-]+year\s+terms\s+unless\s+terminated",
            re.IGNORECASE,
        ),
        "legal_rationale": "Locks the enterprise into multi-year financial commitments through onerous 90+ day silent renewal windows.",
        "suggested_mitigation": "Following the Initial Term, this Agreement shall renew only upon mutual written agreement executed at least thirty (30) days prior to expiration, with mandatory written renewal reminder sixty (60) days in advance.",
    },
    {
        "key": "immediate_termination_no_cure",
        "category": "Immediate Termination Without Cure Window",
        "severity": "HIGH",
        "score": 70.0,
        "pattern": re.compile(
            r"(?:terminate\s+(?:this\s+agreement\s+)?immediately\s+without\s+(?:prior\s+)?(?:notice|cure)|without\s+(?:any\s+)?cure\s+(?:period|window)|immediate\s+termination\s+upon\s+any\s+suspected\s+breach)",
            re.IGNORECASE,
        ),
        "legal_rationale": "Eliminates operational continuity safeguards by allowing sudden cut-off of mission-critical services for minor or remediable issues.",
        "suggested_mitigation": "Either party may terminate this Agreement for material breach only if the breaching party fails to cure such breach within thirty (30) days following receipt of written notice detailing the breach.",
    },
    {
        "key": "unlimited_audit_rights",
        "category": "Unlimited Audit Rights",
        "severity": "MEDIUM",
        "score": 50.0,
        "pattern": re.compile(
            r"(?:audit\s+at\s+any\s+time|unannounced\s+(?:on-site\s+)?audit|unlimited\s+(?:right\s+to\s+)?audit|inspect\s+all\s+facilities\s+without\s+prior\s+notice)",
            re.IGNORECASE,
        ),
        "legal_rationale": "Exposes operations and third-party confidential environments to disruptive, unscheduled inspections at arbitrary frequency.",
        "suggested_mitigation": "Audits may be conducted no more than once per twelve (12) month period upon thirty (30) days advance written notice during normal business hours, subject to standard confidentiality obligations.",
    },
    {
        "key": "asymmetric_fee_shifting",
        "category": "Asymmetric Attorney Fee Shifting",
        "severity": "MEDIUM",
        "score": 45.0,
        "pattern": re.compile(
            r"(?:customer\s+shall\s+(?:solely\s+)?reimburse[^.]*attorneys['’]?\s+fees|regardless\s+of\s+(?:the\s+)?outcome[^.]*(?:legal|attorneys['’]?)\s+fees|one-way\s+attorney\s+fee)",
            re.IGNORECASE,
        ),
        "legal_rationale": "Forces the enterprise to fund counterparty legal fees even when the enterprise prevails or raises good-faith billing disputes.",
        "suggested_mitigation": "In any formal dispute or proceeding arising out of this Agreement, the prevailing party shall be entitled to recover its reasonable outside attorneys' fees and court costs.",
    },
    {
        "key": "non_compete_overbreadth",
        "category": "Non-Compete / Exclusivity Overbreadth",
        "severity": "HIGH",
        "score": 80.0,
        "pattern": re.compile(
            r"(?:worldwide\s+exclusivity|perpetual\s+non-compete|shall\s+not\s+engage\s+with\s+any\s+competing\s+provider|exclusive\s+provider\s+globally\s+for\s+(?:five|ten|\d+)\s+years)",
            re.IGNORECASE,
        ),
        "legal_rationale": "Unlawfully restricts enterprise procurement flexibility and creates antitrust/restraint-of-trade exposure.",
        "suggested_mitigation": "Nothing in this Agreement creates an exclusive relationship or restricts either party from procuring or offering competing products or services, provided Confidential Information is strictly protected.",
    },
    {
        "key": "broad_subprocessor_shield",
        "category": "Broad Data Exfiltration / Subprocessor Shield",
        "severity": "HIGH",
        "score": 75.0,
        "pattern": re.compile(
            r"(?:engage\s+any\s+subprocessor\s+without\s+(?:prior\s+)?notice|no\s+liability\s+for\s+(?:acts\s+or\s+omissions\s+of\s+)?subprocessors|transfer\s+data\s+to\s+any\s+jurisdiction\s+without\s+consent)",
            re.IGNORECASE,
        ),
        "legal_rationale": "Allows unchecked onward data transfers and shields the vendor from breaches caused by its own cloud subcontractors.",
        "suggested_mitigation": "Vendor shall provide thirty (30) days advance written notice prior to authorizing any new subprocessor, permit Customer reasonable objection, and remain fully liable for all subprocessor acts and omissions.",
    },
    {
        "key": "liquidated_damages_trap",
        "category": "Liquidated Damages Penalty Trap",
        "severity": "HIGH",
        "score": 70.0,
        "pattern": re.compile(
            r"(?:liquidated\s+damages\s+(?:equal\s+to|of)\s+(?:200%|300%|all\s+remaining\s+fees)|forfeiture\s+of\s+all\s+prepaid\s+fees|punitive\s+penalty\s+of\s+\$)",
            re.IGNORECASE,
        ),
        "legal_rationale": "Imposes disproportionate punitive penalties decoupled from actual demonstrable harm.",
        "suggested_mitigation": "Any pre-agreed remedies or service credits shall be proportional to actual direct damages incurred and shall not constitute an unenforceable penalty or require forfeiture of unearned prepaid fees.",
    },
]


def _extract_matching_sentence(text: str, match: re.Match[str]) -> str:
    """Expand a regex match to its enclosing sentence or clause paragraph."""
    start = text.rfind(".", 0, match.start())
    start = 0 if start == -1 else start + 1
    end = text.find(".", match.end())
    end = len(text) if end == -1 else end + 1
    sentence = re.sub(r"\s+", " ", text[start:end]).strip()
    if len(sentence) < 25:
        s2 = max(0, match.start() - 60)
        e2 = min(len(text), match.end() + 140)
        sentence = re.sub(r"\s+", " ", text[s2:e2]).strip()
    return sentence


async def auditor_node(state: ContractGraphState) -> ContractGraphState:
    """Scan contract sections against 10 enterprise risk signatures and log Auditor debate turns."""
    start = time.time()
    sections = state.get("sections") or []
    if not sections and state.get("raw_text"):
        sections = [{"section_number": "1", "title": "General Terms", "text": state["raw_text"], "page_number": 1}]

    identified_risks: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for sec in sections:
        sec_num = str(sec.get("section_number", "1"))
        sec_title = str(sec.get("title", "General"))
        sec_text = str(sec.get("text", ""))
        if not sec_text.strip():
            continue

        for sig in RISK_SIGNATURES:
            if sig["key"] in seen_keys:
                continue
            match = sig["pattern"].search(sec_text)
            if match:
                seen_keys.add(sig["key"])
                excerpt = _extract_matching_sentence(sec_text, match)
                identified_risks.append(
                    {
                        "id": f"risk-{uuid.uuid4().hex[:8]}",
                        "key": sig["key"],
                        "category": sig["category"],
                        "severity": sig["severity"],
                        "score": sig["score"],
                        "section_number": sec_num,
                        "section_title": sec_title,
                        "matched_excerpt": excerpt,
                        "legal_rationale": sig["legal_rationale"],
                        "suggested_mitigation": sig["suggested_mitigation"],
                    }
                )

    def _fallback_summary() -> str:
        if not identified_risks:
            return (
                "Completed enterprise compliance audit across all segmented sections. "
                "No severe risk traps matched our 10 canonical exposure signatures."
            )
        cats = ", ".join(f"{r['category']} (Section {r['section_number']}, {r['severity']})" for r in identified_risks)
        return (
            f"Enterprise Compliance Audit identified {len(identified_risks)} material exposure(s): {cats}. "
            "Recommend immediate protective redlines prior to execution to align with corporate risk tolerances."
        )

    prompt = (
        f"Contract: {state.get('title', 'Agreement')}\n"
        f"Playbook: {state.get('playbook_name', 'Standard Corporate Playbook')}\n"
        f"Flagged risks ({len(identified_risks)}): "
        + "; ".join(f"{r['category']} in Section {r['section_number']}" for r in identified_risks)
    )
    llm_resp = await llm_gateway.generate(
        prompt=prompt,
        system_prompt="You are the Enterprise Auditor Agent. Summarize flagged contract exposures concisely in 2 sentences.",
        fallback_fn=_fallback_summary,
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    transcript = list(state.get("debate_transcript") or [])
    transcript.append(
        {
            "agent": "Auditor Agent",
            "role": "Enterprise Defender & Compliance Auditor",
            "section_number": identified_risks[0]["section_number"] if identified_risks else "General",
            "stance": "Protective / Policy Enforcement",
            "message": llm_resp.text,
            "timestamp": now_iso,
        }
    )
    for risk in identified_risks:
        transcript.append(
            {
                "agent": "Auditor Agent",
                "role": "Enterprise Defender & Compliance Auditor",
                "section_number": risk["section_number"],
                "stance": f"Flagged {risk['severity']} Risk",
                "message": f"[{risk['category']}] {risk['legal_rationale']}",
                "timestamp": now_iso,
            }
        )

    total_latency_ms = round((time.time() - start) * 1000.0, 2)
    audit_records = list(state.get("audit_records") or [])
    audit_records.append(
        {
            "agent_name": "Auditor Agent",
            "action": "risk_scan_and_audit",
            "model_name": llm_resp.model_name,
            "prompt_tokens": llm_resp.prompt_tokens,
            "completion_tokens": llm_resp.completion_tokens,
            "total_tokens": llm_resp.total_tokens,
            "latency_ms": max(total_latency_ms, llm_resp.latency_ms),
            "estimated_cost_usd": llm_resp.estimated_cost_usd,
        }
    )

    if state.get("event_emitter"):
        await state["event_emitter"](
            {
                "node": "auditor_node",
                "status": "completed",
                "risks_found": len(identified_risks),
            }
        )

    return {
        **state,
        "identified_risks": identified_risks,
        "debate_transcript": transcript,
        "audit_records": audit_records,
    }
