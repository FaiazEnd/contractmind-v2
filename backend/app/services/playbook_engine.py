"""Corporate Playbook seeding and rule adherence / policy deviation scorer."""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract, Playbook

DEFAULT_PLAYBOOKS: List[Dict[str, Any]] = [
    {
        "name": "Standard Corporate Playbook",
        "description": "Balanced enterprise procurement & commercial risk baseline covering liability caps, data/AI governance, termination cure windows, and dispute terms.",
        "is_default": True,
        "rules": [
            {
                "category": "Limitation of Liability & Consequential Damages",
                "standard_requirement": "Mutual waiver of indirect/consequential damages and aggregate liability capped at 12 months of fees paid.",
                "unacceptable_terms": ["unlimited liability", "uncapped", "no cap on liability", "all indirect and consequential damages", "solely liable without limit"],
                "preferred_fallback": "Mutual cap equal to 12 months fees paid or payable, with mutual waiver of consequential damages except for confidentiality or IP infringement.",
                "severity_if_missing": "CRITICAL",
            },
            {
                "category": "Indemnification Cap & Scope",
                "standard_requirement": "Indemnification obligations must be mutual, tied to third-party claims, and subject to a super-cap or aggregate cap.",
                "unacceptable_terms": ["uncapped indemnification", "indemnify without limitation", "any and all claims whatsoever", "sole negligence"],
                "preferred_fallback": "Third-party IP and bodily injury indemnity capped at 2x annual fees with prompt written notice and defense control.",
                "severity_if_missing": "CRITICAL",
            },
            {
                "category": "AI Model Training & Proprietary Data Rights",
                "standard_requirement": "Vendor may not train foundation or machine learning models on Customer Data or Confidential Information.",
                "unacceptable_terms": ["train its ai", "train machine learning", "improve its artificial intelligence", "perpetual license to customer data", "royalty-free license to train"],
                "preferred_fallback": "Strict prohibition on using Customer Data to train or fine-tune generalized AI/ML models; processing restricted solely to providing contracted services.",
                "severity_if_missing": "CRITICAL",
            },
            {
                "category": "Termination & Cure Period",
                "standard_requirement": "Material breach termination requires written notice and at least a 30-day cure window.",
                "unacceptable_terms": ["terminate immediately without", "without notice or cure", "sole discretion immediately", "no cure period"],
                "preferred_fallback": "Either party may terminate for material breach upon 30 days prior written notice if the breach remains uncured.",
                "severity_if_missing": "HIGH",
            },
            {
                "category": "Renewal & Auto-Renewal Notice",
                "standard_requirement": "Auto-renewal requires at least 30-60 days reminder or opt-out window; no silent multi-year lock-ins.",
                "unacceptable_terms": ["automatically renew for successive 3-year", "irrevocable renewal", "90 days prior notice to prevent", "silent auto-renewal"],
                "preferred_fallback": "Annual renewal unless either party provides written non-renewal notice at least 30 days prior to the end of the then-current term.",
                "severity_if_missing": "MEDIUM",
            },
            {
                "category": "Audit Rights & Data Subprocessors",
                "standard_requirement": "Audits capped at once annually with 30 days notice during business hours; subprocessor changes require advance notice and objection rights.",
                "unacceptable_terms": ["audit at any time without notice", "unannounced on-site", "subprocessors without notice", "no liability for subprocessor"],
                "preferred_fallback": "Annual SOC 2 Type II / ISO 27001 report review plus 30-day advance notice for new subprocessors with right to object.",
                "severity_if_missing": "MEDIUM",
            },
        ],
    },
    {
        "name": "Strict Privacy & AI Governance Playbook",
        "description": "Zero-tolerance data privacy, GDPR/CCPA subprocessor accountability, and strict AI non-training compliance framework.",
        "is_default": False,
        "rules": [
            {
                "category": "AI Training Prohibition",
                "standard_requirement": "Zero customer input/output retention for model training.",
                "unacceptable_terms": ["train", "model weights", "aggregated insights from customer data"],
                "preferred_fallback": "Zero data retention for training; ephemeral inference only.",
                "severity_if_missing": "CRITICAL",
            },
            {
                "category": "Subprocessor Liability & Notification",
                "standard_requirement": "Full flow-down liability for subprocessors and 30-day prior written notice.",
                "unacceptable_terms": ["subprocessors without notice", "disclaims liability for third-party subprocessors"],
                "preferred_fallback": "30-day prior written notification of subprocessor additions with termination right upon reasonable objection.",
                "severity_if_missing": "HIGH",
            },
            {
                "category": "Data Deletion Upon Termination",
                "standard_requirement": "Certified deletion of all Customer Personal Data within 30 days of termination.",
                "unacceptable_terms": ["retain indefinitely", "archival backup exempt indefinitely"],
                "preferred_fallback": "Return and cryptographic deletion within 30 days with written officer certification.",
                "severity_if_missing": "HIGH",
            },
        ],
    },
]


async def ensure_default_playbooks(session: AsyncSession) -> None:
    """Seed default corporate playbooks idempotently."""
    existing = await session.execute(select(Playbook.name))
    existing_names = set(existing.scalars().all())
    added = False
    for pb_data in DEFAULT_PLAYBOOKS:
        if pb_data["name"] not in existing_names:
            session.add(Playbook(**pb_data))
            added = True
    if added:
        await session.commit()


def evaluate_playbook_compliance(contract: Contract, playbook: Playbook) -> Dict[str, Any]:
    """Audit contract text and redline remediations against corporate playbook rules."""
    raw_lower = (contract.raw_text or "").lower()
    redlines: List[Dict[str, Any]] = list(contract.redlines or [])
    rules: List[Dict[str, Any]] = list(playbook.rules or [])

    if not rules:
        return {
            "contract_id": contract.id,
            "playbook_name": playbook.name,
            "adherence_score": 100.0,
            "verdict": "STRONG COMPLIANCE",
            "total_rules": 0,
            "compliant_count": 0,
            "remediated_count": 0,
            "non_compliant_count": 0,
            "rule_checks": [],
        }

    rule_checks: List[Dict[str, Any]] = []
    earned_points = 0.0
    compliant_count = 0
    remediated_count = 0
    non_compliant_count = 0

    for rule in rules:
        category = str(rule.get("category", "Policy Rule"))
        unacceptable_terms = [str(t) for t in (rule.get("unacceptable_terms") or [])]
        severity = str(rule.get("severity_if_missing", "HIGH")).upper()
        fallback = str(rule.get("preferred_fallback", ""))

        matched = [term for term in unacceptable_terms if term.lower() in raw_lower]

        if not matched:
            status = "COMPLIANT"
            earned_points += 1.0
            compliant_count += 1
            remediated_id = None
            finding = "No unacceptable playbook deviations detected in the original agreement text."
        else:
            # Check if an active (non-rejected) redline addresses the clause / matched term
            remediated_id = None
            for rl in redlines:
                if rl.get("accepted") is False:
                    continue
                rl_orig = str(rl.get("original_text", "")).lower()
                rl_sugg = str(rl.get("suggested_text", "")).lower()
                rl_rat = str(rl.get("legal_rationale", "")).lower()
                cat_words = [w for w in category.lower().split() if len(w) > 3]
                if any(m.lower() in rl_orig for m in matched) or any(cw in rl_rat or cw in rl_sugg for cw in cat_words[:2]):
                    # Ensure suggested text actually removes the unacceptable term
                    if not any(m.lower() in rl_sugg for m in matched):
                        remediated_id = rl.get("id")
                        break

            if remediated_id:
                status = "REMEDIATED_BY_REDLINE"
                earned_points += 0.85
                remediated_count += 1
                finding = (
                    f"Original draft triggered policy terms ({', '.join(matched)}); "
                    f"remediated by Consensus Redline {remediated_id}."
                )
            else:
                status = "NON_COMPLIANT"
                non_compliant_count += 1
                finding = f"Policy violation detected ({', '.join(matched)}) without an active remediating redline."

        rule_checks.append(
            {
                "category": category,
                "severity_if_missing": severity,
                "status": status,
                "matched_unacceptable_terms": matched,
                "remediated_by_redline_id": remediated_id,
                "finding": finding,
                "preferred_fallback": fallback,
            }
        )

    score = round((earned_points / len(rules)) * 100.0, 1)
    if score >= 85.0 and non_compliant_count == 0:
        verdict = "STRONG COMPLIANCE"
    elif score >= 60.0:
        verdict = "ACCEPTABLE WITH REDLINES"
    else:
        verdict = "HIGH DEVIATION / HIGH RISK"

    return {
        "contract_id": contract.id,
        "playbook_name": playbook.name,
        "adherence_score": score,
        "verdict": verdict,
        "total_rules": len(rules),
        "compliant_count": compliant_count,
        "remediated_count": remediated_count,
        "non_compliant_count": non_compliant_count,
        "rule_checks": rule_checks,
    }
