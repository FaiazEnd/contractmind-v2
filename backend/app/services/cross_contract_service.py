"""Deal Room cross-contract contradiction & precedence analyzer."""
from __future__ import annotations

import re
from typing import Any


LAW_PATTERNS = [
    ("Delaware", re.compile(r"\bState of Delaware\b|\bDelaware\b", re.IGNORECASE)),
    ("New York", re.compile(r"\bState of New York\b|\bNew York\b", re.IGNORECASE)),
    ("California", re.compile(r"\bState of California\b|\bCalifornia\b", re.IGNORECASE)),
    ("England & Wales", re.compile(r"\bEngland and Wales\b|\bEnglish law\b", re.IGNORECASE)),
    ("Singapore", re.compile(r"\bSingapore\b", re.IGNORECASE)),
    ("Texas", re.compile(r"\bState of Texas\b|\bTexas\b", re.IGNORECASE)),
]

CAP_RE = re.compile(
    r"(?:capped at|not exceed|limited to|maximum liability of)\s+([^\.;\n]{5,90})",
    re.IGNORECASE,
)
NOTICE_DAYS_RE = re.compile(
    r"(\d+)\s*(?:calendar\s+|business\s+)?days(?:\s+prior)?\s+(?:written\s+)?notice",
    re.IGNORECASE,
)


def _extract_contract_profile(contract: Any) -> dict[str, Any]:
    text = getattr(contract, "raw_text", "") or ""
    title = getattr(contract, "title", "Contract")
    cid = getattr(contract, "id", "")

    laws = [name for name, pat in LAW_PATTERNS if pat.search(text)]
    primary_law = laws[0] if laws else "Unspecified"

    uncapped = bool(
        re.search(
            r"unlimited\s+liability|uncapped|without\s+limitation\s+of\s+liability",
            text,
            re.IGNORECASE,
        )
    )
    cap_matches = CAP_RE.findall(text)
    liability_posture = (
        "Uncapped / Unlimited"
        if uncapped
        else (cap_matches[0].strip() if cap_matches else "Standard / Unspecified")
    )

    immediate_term = bool(
        re.search(
            r"terminate\s+immediately\s+without\s+(?:notice|cure)",
            text,
            re.IGNORECASE,
        )
    )
    notice_days = [int(d) for d in NOTICE_DAYS_RE.findall(text)]
    cure_posture = (
        "Immediate (0-day cure)"
        if immediate_term
        else (f"{min(notice_days)}-day notice" if notice_days else "Unspecified")
    )

    has_precedence = bool(
        re.search(r"order\s+of\s+precedence|prevail\s+over|in\s+the\s+event\s+of\s+conflict", text, re.IGNORECASE)
    )
    ai_training_allowed = bool(
        re.search(
            r"(?:train|training)\s+(?:our\s+|its\s+)?(?:ai|artificial\s+intelligence|machine\s+learning)\s+models",
            text,
            re.IGNORECASE,
        )
        and not re.search(
            r"(?:shall\s+not|prohibited\s+from|never)\s+(?:use|train)[^\.]{0,60}(?:ai|machine\s+learning)\s+models",
            text,
            re.IGNORECASE,
        )
    )

    return {
        "id": cid,
        "title": title,
        "governing_law": primary_law,
        "liability_posture": liability_posture,
        "uncapped_liability": uncapped,
        "cure_posture": cure_posture,
        "immediate_termination": immediate_term,
        "notice_days": notice_days,
        "has_precedence": has_precedence,
        "ai_training_allowed": ai_training_allowed,
    }


def analyze_deal_room_conflicts(contracts: list[Any]) -> dict[str, Any]:
    """Evaluate interrelated agreements for conflicting liability caps, governing law traps,
    termination discrepancies, AI data conflicts, and missing order-of-precedence clauses."""
    profiles = [_extract_contract_profile(c) for c in contracts]
    conflicts: list[dict[str, Any]] = []
    penalty_points = 0

    # 1. Governing Law / Jurisdiction Conflict
    distinct_laws = sorted(
        {p["governing_law"] for p in profiles if p["governing_law"] != "Unspecified"}
    )
    if len(distinct_laws) > 1:
        penalty_points += 22
        conflicts.append(
            {
                "id": "conflict_gov_law",
                "category": "Discrepant Governing Law & Jurisdiction",
                "severity": "HIGH",
                "affected_contracts": [
                    f"{p['title']} ({p['governing_law']})" for p in profiles
                ],
                "precedence_risk_explanation": (
                    f"Deal documents specify conflicting jurisdictions ({', '.join(distinct_laws)}). "
                    "Cross-border enforcement or split-venue litigation could invalidate unified remedies."
                ),
                "harmonization_clause": (
                    f"Order of Precedence & Governing Law Harmonization: Notwithstanding any conflicting venue clause in ancillary schedules or addenda, this Master Transaction Suite shall be governed exclusively by the laws of the State of {distinct_laws[0]}, without regard to conflict-of-laws principles."
                ),
            }
        )

    # 2. Limitation of Liability Cap Contradiction
    liability_views = {p["liability_posture"] for p in profiles}
    has_uncapped = any(p["uncapped_liability"] for p in profiles)
    if has_uncapped or len(liability_views) > 1:
        penalty_points += 28 if has_uncapped else 15
        conflicts.append(
            {
                "id": "conflict_liability_cap",
                "category": "Conflicting Limitation of Liability Caps",
                "severity": "CRITICAL" if has_uncapped else "HIGH",
                "affected_contracts": [
                    f"{p['title']}: {p['liability_posture']}" for p in profiles
                ],
                "precedence_risk_explanation": (
                    "One or more agreements expose a party to uncapped or divergent liability ceilings compared to companion agreements, creating an 'escape hatch' around the primary MSA cap."
                ),
                "harmonization_clause": (
                    "Unified Liability Cap Harmonization: Except for proven fraud or willful misconduct, the aggregate cumulative liability of either party across the MSA, all SOWs, and the DPA combined shall not exceed one times (1x) the total fees paid in the twelve (12) months preceding the first claim."
                ),
            }
        )

    # 3. Termination Notice / Cure Window Asymmetry
    cure_views = {p["cure_posture"] for p in profiles}
    has_immediate = any(p["immediate_termination"] for p in profiles)
    if has_immediate or len(cure_views) > 1:
        penalty_points += 18
        conflicts.append(
            {
                "id": "conflict_termination_cure",
                "category": "Asymmetric Termination Notice & Cure Windows",
                "severity": "HIGH",
                "affected_contracts": [
                    f"{p['title']}: {p['cure_posture']}" for p in profiles
                ],
                "precedence_risk_explanation": (
                    "Discrepant termination cure periods allow a party to terminate an ancillary agreement immediately while the parent agreement mandates a 30-day cure period, causing operational stranding."
                ),
                "harmonization_clause": (
                    "Harmonized Termination & Cure Clause: Neither party may terminate this Agreement or any linked Schedule for material breach without delivering written notice specifying the breach and granting a uniform thirty (30) calendar day cure period."
                ),
            }
        )

    # 4. Order of Precedence Trap
    missing_precedence = [p["title"] for p in profiles if not p["has_precedence"]]
    if missing_precedence:
        penalty_points += 15
        conflicts.append(
            {
                "id": "conflict_precedence",
                "category": "Ambiguous Order of Precedence Trap",
                "severity": "MEDIUM",
                "affected_contracts": missing_precedence,
                "precedence_risk_explanation": (
                    f"{len(missing_precedence)} contract(s) lack an explicit Order of Precedence clause. If terms clash between an MSA, SOW, and DPA, courts may apply the 'last-in-time' rule against enterprise intent."
                ),
                "harmonization_clause": (
                    "Standard Order of Precedence: In the event of any conflict among the deal documents, the following descending order of precedence shall control: (1) Data Processing Addendum (solely as to privacy/security), (2) Master Services Agreement, and (3) individual Statements of Work or Order Forms."
                ),
            }
        )

    # 5. AI Data Rights Cross-Document Leak
    ai_allow = [p["title"] for p in profiles if p["ai_training_allowed"]]
    ai_forbid = [p["title"] for p in profiles if not p["ai_training_allowed"]]
    if ai_allow and ai_forbid:
        penalty_points += 17
        conflicts.append(
            {
                "id": "conflict_ai_data",
                "category": "Cross-Agreement AI Data Training Leakage",
                "severity": "CRITICAL",
                "affected_contracts": [
                    f"Permits AI Training: {', '.join(ai_allow)}",
                    f"Restricts/Silent: {', '.join(ai_forbid)}",
                ],
                "precedence_risk_explanation": (
                    "An ancillary SaaS/Order document permits AI model training on tenant inputs even though companion agreements treat customer content as strictly confidential."
                ),
                "harmonization_clause": (
                    "AI Training Prohibition Override: Notwithstanding any click-through terms, telemetry clause, or Order Form provision, Vendor shall not use Customer Data or Confidential Information to train, fine-tune, or validate artificial intelligence models."
                ),
            }
        )

    deal_alignment_score = round(max(10.0, 100.0 - penalty_points), 1)
    return {
        "deal_alignment_score": deal_alignment_score,
        "contracts_evaluated": len(profiles),
        "contract_profiles": profiles,
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "summary": (
            "Deal documents are strongly aligned with minor harmonization recommended."
            if deal_alignment_score >= 80
            else "Material cross-contract contradictions detected; adopt harmonization clauses before execution."
        ),
    }
