"""Auditor Agent: Enterprise compliance defender scanning sections against 10 risk categories."""
from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.agents.llm_client import llm_gateway
from app.agents.state import ContractAnalysisState


RISK_RULES: list[dict[str, Any]] = [
    {
        "category": "Uncapped Indemnification",
        "severity": "CRITICAL",
        "score": 90,
        "pattern": re.compile(
            r"(?:indemnif(?:y|ication)|hold\s+harmless).{0,220}?(?:without\s+limitation|unlimited|uncapped|all\s+claims\s+whatsoever|regardless\s+of\s+cap)",
            re.IGNORECASE | re.DOTALL,
        ),
        "legal_rationale": (
            "Clause imposes uncapped or unlimited indemnification liability without a negotiated monetary ceiling or fault nexus, exposing the balance sheet to existential loss."
        ),
        "suggested_mitigation": (
            "Cap third-party indemnification obligations at two times (2x) annual contract fees, conditioned upon prompt written notice, reasonable cooperation, and sole defense control."
        ),
        "consensus_replacement": (
            "Each party shall defend, indemnify, and hold harmless the other party from third-party intellectual property infringement or bodily injury claims directly caused by the indemnifying party's gross negligence or willful misconduct, subject to an aggregate liability super-cap equal to two times (2x) the total fees paid under this Agreement in the preceding twelve (12) months, conditioned on prompt written notice and sole control of defense."
        ),
    },
    {
        "category": "Consequential Damages Waiver Missing",
        "severity": "HIGH",
        "score": 75,
        "pattern": re.compile(
            r"(?:consequential|indirect|special|punitive|incidental)\s+damages.{0,180}?(?:shall\s+be\s+recoverable|not\s+excluded|excluded\s+solely\s+for\s+(?:vendor|provider)|only\s+vendor\s+shall\s+not)",
            re.IGNORECASE | re.DOTALL,
        ),
        "legal_rationale": (
            "Agreement fails to establish a mutual waiver of indirect, consequential, or lost-profit damages, or shields only the counterparty."
        ),
        "suggested_mitigation": (
            "Insert a bilateral waiver excluding indirect, incidental, consequential, and punitive damages for both parties."
        ),
        "consensus_replacement": (
            "NEITHER PARTY SHALL BE LIABLE TO THE OTHER FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, EXEMPLARY, OR PUNITIVE DAMAGES, OR FOR ANY LOSS OF PROFITS, REVENUE, OR DATA, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGES, AND AGGREGATE DIRECT LIABILITY SHALL NOT EXCEED TWELVE (12) MONTHS OF FEES PAID."
        ),
    },
    {
        "category": "AI Model Training on Proprietary Data",
        "severity": "CRITICAL",
        "score": 95,
        "pattern": re.compile(
            r"(?:train|training|fine-tun(?:e|ing)|improv(?:e|ing))\s+(?:our\s+|its\s+|generalized\s+)?(?:artificial\s+intelligence|ai|machine\s+learning|llm|foundation)\s+models|(?:perpetual|irrevocable|royalty-free)\s+license\s+to\s+(?:use|reproduce|train).{0,100}?(?:customer\s+data|inputs|prompts|content)",
            re.IGNORECASE | re.DOTALL,
        ),
        "legal_rationale": (
            "Counterparty claims a broad right to use proprietary Customer Data, prompts, or confidential inputs to train external AI/ML models, risking IP leakage and trade secret loss."
        ),
        "suggested_mitigation": (
            "Explicitly prohibit using Customer Data, prompts, or outputs to train, fine-tune, or evaluate any generalized or third-party AI/ML models."
        ),
        "consensus_replacement": (
            "Customer retains all right, title, and interest in and to Customer Data, prompts, and outputs. Provider is strictly prohibited from using, retaining, or processing Customer Data or Confidential Information to train, fine-tune, validate, or improve any generalized or third-party artificial intelligence or machine learning models."
        ),
    },
    {
        "category": "Auto-Renewal Without Notice Trap",
        "severity": "MEDIUM",
        "score": 55,
        "pattern": re.compile(
            r"(?:auto-?renew|automatically\s+renew).{0,180}?(?:without\s+(?:prior\s+)?notice|unless\s+terminated\s+(?:90|120)\s+days|successive\s+(?:three|3|two|2)-?year)",
            re.IGNORECASE | re.DOTALL,
        ),
        "legal_rationale": (
            "Evergreen automatic renewal locks the enterprise into multi-year commitments without mandatory advance vendor notice or reasonable opt-out window."
        ),
        "suggested_mitigation": (
            "Require 60-day advance written renewal reminder from Vendor and reduce Customer non-renewal notice window to 30 days."
        ),
        "consensus_replacement": (
            "Following the Initial Term, this Agreement may renew for successive one (1) year periods only if Provider delivers a written renewal reminder at least sixty (60) days prior to expiration and Customer does not provide written notice of non-renewal at least thirty (30) days prior to the renewal date."
        ),
    },
    {
        "category": "Immediate Termination Without Cure Window",
        "severity": "HIGH",
        "score": 70,
        "pattern": re.compile(
            r"terminat(?:e|ion).{0,160}?(?:immediately\s+without\s+(?:prior\s+)?(?:notice|cure)|without\s+(?:any\s+)?cure\s+(?:period|window)|at\s+its\s+sole\s+discretion\s+without\s+notice)",
            re.IGNORECASE | re.DOTALL,
        ),
        "legal_rationale": (
            "Grants counterparty unilateral right to terminate mission-critical services immediately without notice or opportunity to remediate alleged breaches."
        ),
        "suggested_mitigation": (
            "Mandate written notice detailing the alleged breach and a thirty (30) calendar day cure window before termination takes effect."
        ),
        "consensus_replacement": (
            "Either party may terminate this Agreement for material breach only if the breaching party fails to cure such breach within thirty (30) calendar days after receiving detailed written notice specifying the nature of the breach, with pro-rata refund of prepaid unearned fees upon termination for Provider breach."
        ),
    },
    {
        "category": "Unlimited Audit Rights",
        "severity": "MEDIUM",
        "score": 50,
        "pattern": re.compile(
            r"audit.{0,180}?(?:at\s+any\s+time|unlimited\s+audit|without\s+prior\s+notice|sole\s+expense\s+of\s+(?:customer|company)|unrestricted\s+access)",
            re.IGNORECASE | re.DOTALL,
        ),
        "legal_rationale": (
            "Permits invasive, unscheduled, unlimited on-site inspections at the company's sole cost, disrupting operations and exposing unrelated systems."
        ),
        "suggested_mitigation": (
            "Restrict audits to once per 12 months with 30 days prior written notice during business hours, satisfiable via SOC 2 Type II report."
        ),
        "consensus_replacement": (
            "Each party may conduct a compliance audit no more than once per twelve (12) months upon thirty (30) days advance written notice during normal business hours at the auditing party's expense; provided that delivery of an independent SOC 2 Type II or ISO 27001 attestation shall satisfy routine audit requirements."
        ),
    },
    {
        "category": "Asymmetric Attorney Fee Shifting",
        "severity": "MEDIUM",
        "score": 45,
        "pattern": re.compile(
            r"(?:attorneys['\u2019]?\s+fees|legal\s+fees).{0,160}?(?:solely\s+by\s+(?:customer|buyer|licensee)|only\s+(?:vendor|provider|seller)\s+shall\s+recover|shall\s+reimburse\s+(?:provider|vendor|seller)\s+regardless)",
            re.IGNORECASE | re.DOTALL,
        ),
        "legal_rationale": (
            "One-sided fee-shifting clause obligates only one party to pay all legal and collection costs even if the counterparty does not prevail."
        ),
        "suggested_mitigation": (
            "Convert to bilateral prevailing-party attorney fee recovery or each party bears its own legal expenses."
        ),
        "consensus_replacement": (
            "In any formal action or proceeding to enforce rights under this Agreement, the substantially prevailing party as determined by final non-appealable judgment shall be entitled to recover its reasonable outside attorneys' fees and court costs."
        ),
    },
    {
        "category": "Non-Compete / Exclusivity Overbreadth",
        "severity": "HIGH",
        "score": 80,
        "pattern": re.compile(
            r"(?:non-?compet(?:e|ition)|exclusiv(?:e|ity)).{0,180}?(?:perpetual|worldwide|any\s+(?:software|technology|business)\s+whatsoever|(?:five|5|ten|10)\s+years|prohibited\s+from\s+engaging\s+any\s+other)",
            re.IGNORECASE | re.DOTALL,
        ),
        "legal_rationale": (
            "Overbroad exclusivity or multi-year worldwide non-compete restricts core business operations and risks antitrust or enforceability invalidation."
        ),
        "suggested_mitigation": (
            "Narrow restrictive covenant to directly competing commercial lines for a maximum duration of twenty-four (24) months within agreed territories."
        ),
        "consensus_replacement": (
            "Any non-competition or exclusivity restriction hereunder shall apply solely to directly competing product offerings within the defined commercial vertical for a period not to exceed twenty-four (24) months from Closing, and shall not restrict independent internal development or existing passive investments."
        ),
    },
    {
        "category": "Broad Data Exfiltration / Subprocessor Shield",
        "severity": "HIGH",
        "score": 75,
        "pattern": re.compile(
            r"(?:subprocessor|third-party\s+processor|transfer\s+personal\s+data).{0,180}?(?:without\s+(?:prior\s+)?notice|no\s+liability\s+for\s+subprocessor|shielded\s+from\s+liability|any\s+jurisdiction\s+without\s+safeguards)",
            re.IGNORECASE | re.DOTALL,
        ),
        "legal_rationale": (
            "Permits onboarding arbitrary subprocessors and cross-border data transfers without prior notice, objection rights, or flow-down liability."
        ),
        "suggested_mitigation": (
            "Mandate 30-day advance written notice of new subprocessors, Customer objection rights, Standard Contractual Clauses, and full Processor flow-down liability."
        ),
        "consensus_replacement": (
            "Processor shall not engage any new subprocessor or transfer Personal Data cross-border without thirty (30) days prior written notice to Customer, an opportunity for Customer to object on reasonable data-protection grounds, execution of Standard Contractual Clauses, and Processor's full primary liability for all subprocessor acts and omissions."
        ),
    },
    {
        "category": "Liquidated Damages Penalty Trap",
        "severity": "HIGH",
        "score": 70,
        "pattern": re.compile(
            r"(?:liquidated\s+damages|early\s+termination\s+fee|penalty\s+multiplier).{0,180}?(?:100%\s+of\s+remaining|three\s+times|3x|10x|punitive|immediately\s+accelerated)",
            re.IGNORECASE | re.DOTALL,
        ),
        "legal_rationale": (
            "Imposes punitive liquidated damages or full contract acceleration penalties disproportionate to actual administrative harm."
        ),
        "suggested_mitigation": (
            "Replace punitive fee acceleration with proportionate service credits or capped documented direct transition costs."
        ),
        "consensus_replacement": (
            "In no event shall either party be subject to punitive liquidated damages or full fee acceleration upon termination for cause; any termination settlement or SLA remedy shall be limited to documented direct transition wind-down expenses or proportionate service credits capped at fifteen percent (15%) of monthly recurring fees."
        ),
    },
]


async def auditor_node(state: ContractAnalysisState) -> ContractAnalysisState:
    """Scan contract sections against 10 enterprise risk categories and log Auditor arguments."""
    t0 = time.time()
    cb = state.get("progress_callback")
    if cb:
        await cb({"stage": "auditor", "status": "running", "message": "Auditor Agent scanning clauses for 10 risk categories..."})

    sections = state.get("sections") or []
    identified_risks: list[dict[str, Any]] = []
    debate_transcript: list[dict[str, Any]] = list(state.get("debate_transcript") or [])
    risk_summary = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    seen_pairs: set[tuple[str, str]] = set()

    for sec in sections:
        sec_num = str(sec.get("section_number", "1"))
        sec_title = str(sec.get("title", "Clause"))
        sec_text = str(sec.get("text", ""))
        if not sec_text.strip():
            continue

        for rule in RISK_RULES:
            match = rule["pattern"].search(sec_text)
            if match:
                key = (sec_num, rule["category"])
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)

                sev = rule["severity"].upper()
                sev_key = sev.lower()
                if sev_key in risk_summary:
                    risk_summary[sev_key] += 1

                risk_id = f"risk_{uuid.uuid4().hex[:8]}"
                finding = {
                    "id": risk_id,
                    "category": rule["category"],
                    "severity": sev,
                    "score": rule["score"],
                    "section_number": sec_num,
                    "section_title": sec_title,
                    "matched_excerpt": sec_text,
                    "legal_rationale": rule["legal_rationale"],
                    "suggested_mitigation": rule["suggested_mitigation"],
                    "consensus_replacement": rule["consensus_replacement"],
                }
                identified_risks.append(finding)

    # Also invoke LLM Gateway once to synthesize an Auditor Executive Risk Opening (with zero-failure fallback)
    risk_list_text = "\n".join(
        f"- [Section {r['section_number']}] {r['category']} ({r['severity']}): {r['legal_rationale']}"
        for r in identified_risks
    ) or "No critical deviations flagged."

    fallback_opening = (
        f"Auditor Agent completed a compliance sweep across {len(sections)} contract sections "
        f"under '{state.get('playbook_name', 'Standard Corporate Playbook')}'. "
        f"Identified {len(identified_risks)} material risk(s): "
        f"{risk_summary['critical']} Critical, {risk_summary['high']} High, {risk_summary['medium']} Medium. "
        "Immediate remediation is required to cap uncapped liabilities, block AI model training on proprietary data, and restore bilateral cure protections."
    )

    llm_res = await llm_gateway.generate(
        prompt=(
            f"You are the Enterprise Auditor Agent reviewing '{state.get('title', 'Contract')}'.\n"
            f"Detected Risks:\n{risk_list_text}\n\n"
            "Write a concise 3-sentence legal opening statement demanding remediation."
        ),
        system_prompt="You are a rigorous Enterprise Legal Compliance Auditor.",
        fallback_text=fallback_opening,
    )

    ts = datetime.now(timezone.utc).isoformat()
    debate_transcript.append(
        {
            "agent": "Auditor Agent",
            "role": "Enterprise Compliance Defender",
            "section_number": "ALL",
            "category": "Portfolio Risk Sweep",
            "argument": llm_res.text,
            "timestamp": ts,
        }
    )

    for r in identified_risks:
        debate_transcript.append(
            {
                "agent": "Auditor Agent",
                "role": "Enterprise Compliance Defender",
                "section_number": r["section_number"],
                "category": r["category"],
                "argument": (
                    f"[{r['severity']}] Flagged Section {r['section_number']} ({r['section_title']}): "
                    f"{r['legal_rationale']} Recommended action: {r['suggested_mitigation']}"
                ),
                "timestamp": ts,
            }
        )

    elapsed_ms = round((time.time() - t0) * 1000.0, 2)
    audit_logs = list(state.get("audit_logs") or [])
    audit_logs.append(
        {
            "agent_name": "Auditor Agent",
            "action": "risk_audit_scan",
            "model_name": llm_res.model,
            "prompt_tokens": llm_res.prompt_tokens,
            "completion_tokens": llm_res.completion_tokens,
            "total_tokens": llm_res.total_tokens,
            "latency_ms": max(elapsed_ms, llm_res.latency_ms),
            "estimated_cost_usd": llm_res.estimated_cost_usd,
        }
    )

    if cb:
        await cb(
            {
                "stage": "auditor",
                "status": "completed",
                "message": f"Auditor Agent flagged {len(identified_risks)} risks.",
            }
        )

    return {
        **state,
        "identified_risks": identified_risks,
        "risk_summary": risk_summary,
        "debate_transcript": debate_transcript,
        "audit_logs": audit_logs,
    }
