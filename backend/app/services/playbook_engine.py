"""Playbook rule adherence and policy deviation scoring engine."""

from __future__ import annotations

from typing import Any

from app.schemas.playbook_schemas import PlaybookComplianceResult, RuleComplianceItem


_SEVERITY_WEIGHTS: dict[str, float] = {
    "CRITICAL": 3.0,
    "HIGH": 2.0,
    "MEDIUM": 1.5,
    "LOW": 1.0,
}

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "indemnification": ["indemnif", "hold harmless", "liability cap", "aggregate liability"],
    "consequential": ["consequential", "indirect", "incidental", "lost profits", "punitive"],
    "ai": ["artificial intelligence", "machine learning", "ai model", "foundation model", "customer data"],
    "termination": ["terminate", "termination", "cure", "written notice", "material breach"],
    "renewal": ["renew", "renewal", "auto-renew", "automatically renew", "non-renewal"],
    "audit": ["audit", "inspect", "records", "business hours", "compliance"],
    "subprocessor": ["subprocessor", "sub-processor", "third party", "gdpr", "dpa"],
    "non-compete": ["non-compete", "exclusivity", "exclusive", "competing"],
    "attorney": ["attorneys' fees", "attorney fees", "legal fees", "prevailing party"],
    "liquidated": ["liquidated damages", "penalty", "service credit", "forfeiture"],
}


def _find_matching_redlines(rule: dict[str, Any], redlines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cat_lower = rule.get("category", "").lower()
    keywords = []
    for key, kws in _CATEGORY_KEYWORDS.items():
        if key in cat_lower:
            keywords.extend(kws)
    if not keywords:
        keywords = [w for w in cat_lower.split() if len(w) > 3]

    matches = []
    for rl in redlines:
        combined = " ".join(
            [
                str(rl.get("legal_rationale", "")),
                str(rl.get("original_text", "")),
                str(rl.get("suggested_text", "")),
            ]
        ).lower()
        if any(kw in combined for kw in keywords):
            matches.append(rl)
    return matches


def evaluate_playbook_compliance(contract: Any, playbook: Any) -> PlaybookComplianceResult:
    """Audit contract text & arbiter redlines against assigned corporate playbook rules."""
    raw_text = (getattr(contract, "raw_text", "") or "").lower()
    redlines = getattr(contract, "redlines", None) or []
    rules = getattr(playbook, "rules", None) or []
    playbook_name = getattr(playbook, "name", None) or getattr(contract, "playbook_name", "Standard Corporate Playbook")

    checklist: list[RuleComplianceItem] = []
    total_weight = 0.0
    earned_weight = 0.0
    compliant_count = 0
    remediated_count = 0
    deviation_count = 0

    for rule in rules:
        rule_id = str(rule.get("id", ""))
        category = str(rule.get("category", "Policy Rule"))
        severity = str(rule.get("severity_if_missing", "HIGH")).upper()
        std_req = str(rule.get("standard_requirement", ""))
        unacceptable = [str(t) for t in (rule.get("unacceptable_terms") or [])]
        fallback = str(rule.get("preferred_fallback", ""))

        weight = _SEVERITY_WEIGHTS.get(severity, 1.5)
        total_weight += weight

        matched_bad = [term for term in unacceptable if term.lower() in raw_text]
        matching_redlines = _find_matching_redlines(rule, redlines)
        active_redlines = [r for r in matching_redlines if r.get("accepted") is not False]

        if not matched_bad:
            # Check if standard topic is addressed or no unacceptable terms triggered
            status = "COMPLIANT"
            compliant_count += 1
            earned_weight += weight
            note = "No prohibited playbook terms detected in agreement."
        elif active_redlines:
            # Verify redline suggested text avoids unacceptable terms
            remediated_clean = any(
                not any(term.lower() in str(r.get("suggested_text", "")).lower() for term in unacceptable)
                for r in active_redlines
            )
            if remediated_clean:
                status = "REMEDIATED_BY_REDLINE"
                remediated_count += 1
                # Full credit if accepted, 85% credit if proposed pending acceptance
                accepted_any = any(r.get("accepted") is True for r in active_redlines)
                earned_weight += weight * (1.0 if accepted_any else 0.85)
                note = (
                    "Arbiter redline accepted and remediates policy deviation."
                    if accepted_any
                    else "Arbiter redline proposed to remediate policy deviation (pending acceptance)."
                )
            else:
                status = "DEVIATION"
                deviation_count += 1
                note = "Flagged deviation not yet fully resolved by current redline text."
        else:
            status = "DEVIATION"
            deviation_count += 1
            note = "Unacceptable playbook terms present without active remediation redline."

        checklist.append(
            RuleComplianceItem(
                rule_id=rule_id,
                category=category,
                severity=severity,
                standard_requirement=std_req,
                status=status,
                matched_unacceptable_terms=matched_bad,
                remediation_note=note,
                preferred_fallback=fallback,
            )
        )

    adherence_score = round((earned_weight / total_weight) * 100.0, 1) if total_weight > 0 else 100.0

    if adherence_score >= 80.0 and deviation_count == 0:
        verdict = "STRONG COMPLIANCE"
    elif adherence_score >= 55.0:
        verdict = "ACCEPTABLE WITH REDLINES"
    else:
        verdict = "HIGH DEVIATION / HIGH RISK"

    return PlaybookComplianceResult(
        contract_id=str(getattr(contract, "id", "")),
        playbook_name=playbook_name,
        adherence_score=adherence_score,
        verdict=verdict,
        total_rules=len(rules),
        compliant_count=compliant_count,
        remediated_count=remediated_count,
        deviation_count=deviation_count,
        checklist=checklist,
    )
