"""Playbook rule adherence & policy deviation scorer."""
from __future__ import annotations

from typing import Any


def evaluate_playbook_compliance(
    contract: Any, playbook: Any | None
) -> dict[str, Any]:
    """Audit contract text and redline remediation against assigned corporate playbook rules."""
    contract_id = getattr(contract, "id", "")
    raw_text = (getattr(contract, "raw_text", "") or "").lower()
    redlines: list[dict[str, Any]] = list(getattr(contract, "redlines", None) or [])
    playbook_name = (
        getattr(playbook, "name", None)
        or getattr(contract, "playbook_name", "Standard Corporate Playbook")
    )
    rules: list[dict[str, Any]] = list(getattr(playbook, "rules", None) or [])

    if not rules:
        return {
            "contract_id": contract_id,
            "playbook_name": playbook_name,
            "adherence_score": 100.0,
            "status_verdict": "STRONG COMPLIANCE",
            "passed_rules": 0,
            "total_rules": 0,
            "rule_checks": [],
        }

    # Build combined remediated text from redlines (accepted or proposed)
    remediated_texts = " ".join(
        str(rl.get("suggested_text", "")).lower()
        for rl in redlines
        if rl.get("accepted") is not False
    )
    accepted_texts = " ".join(
        str(rl.get("suggested_text", "")).lower()
        for rl in redlines
        if rl.get("accepted") is True
    )

    rule_checks: list[dict[str, Any]] = []
    score_sum = 0.0
    passed_count = 0

    for rule in rules:
        category = rule.get("category", "Policy Rule")
        standard_req = rule.get("standard_requirement", "")
        unacceptable = [t.lower() for t in (rule.get("unacceptable_terms") or [])]
        preferred_fallback = rule.get("preferred_fallback", "")
        severity = str(rule.get("severity_if_missing", "HIGH")).upper()

        matched_violations = [term for term in unacceptable if term and term in raw_text]

        # Check if redlines remediate the deviation
        category_tokens = [w for w in category.lower().split() if len(w) > 3]
        matching_redlines = [
            rl
            for rl in redlines
            if any(
                tok in (str(rl.get("legal_rationale", "")) + " " + str(rl.get("suggested_text", ""))).lower()
                for tok in category_tokens
            )
        ]

        remediated_by_arbiter = False
        remediated_and_accepted = False
        if matching_redlines:
            remediated_by_arbiter = any(
                rl.get("accepted") is not False for rl in matching_redlines
            )
            remediated_and_accepted = any(
                rl.get("accepted") is True for rl in matching_redlines
            )
        elif matched_violations and remediated_texts:
            # Fallback check: suggested redline eliminates the unacceptable phrase
            for rl in redlines:
                if rl.get("accepted") is not False:
                    orig_l = str(rl.get("original_text", "")).lower()
                    sugg_l = str(rl.get("suggested_text", "")).lower()
                    if any(v in orig_l and v not in sugg_l for v in matched_violations):
                        remediated_by_arbiter = True
                        if rl.get("accepted") is True:
                            remediated_and_accepted = True

        if not matched_violations:
            status = "COMPLIANT"
            rule_score = 100.0
            passed_count += 1
            remediation_note = "Original text satisfies corporate playbook baseline."
        elif remediated_and_accepted:
            status = "REMEDIATED_ACCEPTED"
            rule_score = 95.0
            passed_count += 1
            remediation_note = "Deviation flagged and remediated via accepted Arbiter redline."
        elif remediated_by_arbiter:
            status = "REMEDIATED_PENDING"
            rule_score = 75.0
            passed_count += 1
            remediation_note = "Unacceptable term detected; Arbiter consensus redline drafted (pending lawyer acceptance)."
        else:
            status = "NON_COMPLIANT"
            penalty = {"CRITICAL": 15.0, "HIGH": 25.0, "MEDIUM": 40.0, "LOW": 60.0}.get(
                severity, 25.0
            )
            rule_score = penalty
            remediation_note = (
                f"Detected policy violation(s): {', '.join(matched_violations)}. "
                "Apply preferred fallback language."
            )

        score_sum += rule_score
        rule_checks.append(
            {
                "category": category,
                "standard_requirement": standard_req,
                "severity": severity,
                "status": status,
                "score": rule_score,
                "matched_violations": matched_violations,
                "remediated": remediated_by_arbiter,
                "remediated_accepted": remediated_and_accepted,
                "remediation_note": remediation_note,
                "preferred_fallback": preferred_fallback,
            }
        )

    adherence_score = round(score_sum / len(rules), 1)
    if adherence_score >= 80.0:
        verdict = "STRONG COMPLIANCE"
    elif adherence_score >= 55.0:
        verdict = "ACCEPTABLE WITH REDLINES"
    else:
        verdict = "HIGH DEVIATION / HIGH RISK"

    return {
        "contract_id": contract_id,
        "playbook_name": playbook_name,
        "adherence_score": adherence_score,
        "status_verdict": verdict,
        "passed_rules": passed_count,
        "total_rules": len(rules),
        "rule_checks": rule_checks,
    }
