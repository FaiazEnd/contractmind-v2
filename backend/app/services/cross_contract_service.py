"""Deal Room Cross-Contract Contradiction & Precedence Analyzer."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from app.models.contract import Contract

_LAW_RE = re.compile(
    r"(?:governed by|laws of(?: the)?(?: State of)?)\s+(Delaware|New York|California|Texas|England and Wales|Singapore|Ireland)",
    re.IGNORECASE,
)
_CAP_RE = re.compile(
    r"(?:aggregate liability|liability.*?shall not exceed|capped at|maximum liability).*?(\$[\d,]+(?:\.\d+)?|\d+\s+months?(?:\s+of)?\s+fees|unlimited|uncapped)",
    re.IGNORECASE | re.DOTALL,
)
_CURE_RE = re.compile(
    r"(?:cure(?:\s+period|\s+within)?|written notice.*?)(\d+\s*(?:calendar|business)?\s*days?)|terminate immediately without",
    re.IGNORECASE,
)
_PRECEDENCE_RE = re.compile(
    r"(?:order of precedence|in the event of a conflict|shall prevail over|supersedes)",
    re.IGNORECASE,
)


def _extract_snippet(text: str, pattern: re.Pattern[str]) -> str | None:
    m = pattern.search(text or "")
    if not m:
        return None
    start = max(0, m.start() - 40)
    end = min(len(text), m.end() + 80)
    return " ".join(text[start:end].split())


def analyze_cross_contract_conflicts(contracts: List[Contract]) -> Dict[str, Any]:
    """Evaluate multiple related contracts for conflicting caps, governing law, termination, and precedence traps."""
    if len(contracts) < 2:
        return {
            "deal_alignment_score": 100.0,
            "contract_count": len(contracts),
            "conflicts": [],
            "summary": "Select at least two agreements to audit cross-contract contradictions.",
        }

    conflicts: List[Dict[str, Any]] = []

    # 1. Governing Law & Jurisdiction check
    laws_found: Dict[str, List[str]] = {}
    for c in contracts:
        m = _LAW_RE.search(c.raw_text or "")
        if m:
            jurisdiction = m.group(1).strip().title()
            laws_found.setdefault(jurisdiction, []).append(c.title)

    if len(laws_found) > 1:
        conflicts.append(
            {
                "id": "conflict-governing-law",
                "conflict_type": "Discrepant Governing Law & Forum Trap",
                "severity": "HIGH",
                "involved_contracts": [c.title for c in contracts],
                "conflicting_terms": {k: v for k, v in laws_found.items()},
                "precedence_risk_explanation": (
                    "Related deal documents specify conflicting governing jurisdictions "
                    f"({', '.join(laws_found.keys())}), creating split-forum litigation exposure."
                ),
                "harmonization_clause": (
                    "All Schedules, SOWs, and Data Processing Addenda executed hereunder shall be governed exclusively "
                    "by the laws of the State of Delaware, without regard to conflict-of-laws principles, superseding "
                    "any contrary venue clause in ancillary attachments."
                ),
            }
        )

    # 2. Limitation of Liability Cap divergence
    cap_profiles: List[Dict[str, str]] = []
    for c in contracts:
        text = c.raw_text or ""
        m = _CAP_RE.search(text)
        if m:
            cap_val = (m.group(1) or "uncapped").strip()
            cap_profiles.append({"contract": c.title, "cap": cap_val})
        elif "unlimited liability" in text.lower() or "uncapped" in text.lower():
            cap_profiles.append({"contract": c.title, "cap": "Uncapped / Unlimited"})

    distinct_caps = {p["cap"].lower() for p in cap_profiles}
    if len(distinct_caps) > 1:
        conflicts.append(
            {
                "id": "conflict-liability-cap",
                "conflict_type": "Conflicting Limitation of Liability Caps",
                "severity": "CRITICAL",
                "involved_contracts": [p["contract"] for p in cap_profiles],
                "conflicting_terms": {p["contract"]: p["cap"] for p in cap_profiles},
                "precedence_risk_explanation": (
                    "Liability caps diverge across deal agreements. An uncapped or higher-cap ancillary addendum "
                    "can silently pierce the primary Master Agreement's liability ceiling."
                ),
                "harmonization_clause": (
                    "Notwithstanding anything to the contrary in any SOW, Order Form, or DPA, each party's aggregate "
                    "cumulative liability across all Transaction Documents shall not exceed 12 months of total fees paid "
                    "under the applicable Master Agreement, except for gross negligence or willful misconduct."
                ),
            }
        )

    # 3. Termination & Cure Window Asymmetry
    cure_profiles: List[Dict[str, str]] = []
    for c in contracts:
        text = c.raw_text or ""
        m = _CURE_RE.search(text)
        if m:
            val = m.group(1) if m.group(1) else "Immediate termination (0-day cure)"
            cure_profiles.append({"contract": c.title, "cure": val.strip()})

    distinct_cures = {p["cure"].lower() for p in cure_profiles}
    if len(distinct_cures) > 1:
        conflicts.append(
            {
                "id": "conflict-termination-cure",
                "conflict_type": "Asymmetric Termination Notice & Cure Windows",
                "severity": "HIGH",
                "involved_contracts": [p["contract"] for p in cure_profiles],
                "conflicting_terms": {p["contract"]: p["cure"] for p in cure_profiles},
                "precedence_risk_explanation": (
                    "One agreement permits immediate termination without cure while a companion agreement mandates "
                    "a multi-week cure period, creating an accidental cross-default trigger."
                ),
                "harmonization_clause": (
                    "Termination for material breach of any ancillary Schedule or SOW shall require thirty (30) days "
                    "prior written notice and opportunity to cure, aligned uniformly with the Master Agreement."
                ),
            }
        )

    # 4. Ambiguous Order of Precedence Trap
    precedence_hits: List[Dict[str, str]] = []
    for c in contracts:
        snippet = _extract_snippet(c.raw_text or "", _PRECEDENCE_RE)
        if snippet:
            precedence_hits.append({"contract": c.title, "clause": snippet})

    if len(precedence_hits) >= 1 and any(
        "prevail over the master" in h["clause"].lower() or "supersedes the msa" in h["clause"].lower()
        for h in precedence_hits
    ):
        conflicts.append(
            {
                "id": "conflict-order-of-precedence",
                "conflict_type": "Inverted Order of Precedence Trap",
                "severity": "CRITICAL",
                "involved_contracts": [h["contract"] for h in precedence_hits],
                "conflicting_terms": {h["contract"]: h["clause"] for h in precedence_hits},
                "precedence_risk_explanation": (
                    "An ancillary document claims precedence over the Master Agreement, potentially overriding "
                    "enterprise-negotiated indemnities, liability caps, and IP protections."
                ),
                "harmonization_clause": (
                    "In the event of any conflict, the following descending order of precedence shall apply: "
                    "(1) the Data Processing Addendum solely for privacy/GDPR terms, (2) the Master Services Agreement, "
                    "and (3) the applicable Statement of Work or Order Form."
                ),
            }
        )
    elif not precedence_hits:
        conflicts.append(
            {
                "id": "conflict-missing-precedence",
                "conflict_type": "Missing Order of Precedence Hierarchy",
                "severity": "MEDIUM",
                "involved_contracts": [c.title for c in contracts],
                "conflicting_terms": {c.title: "No explicit conflict-precedence hierarchy clause found" for c in contracts},
                "precedence_risk_explanation": (
                    "None of the selected agreements establish a clear contractual order of precedence, leaving "
                    "conflicting commercial or SLA clauses ambiguous."
                ),
                "harmonization_clause": (
                    "Order of Precedence: In the event of conflict among transaction documents, the Master Agreement "
                    "shall control unless an Order Form explicitly cites the specific Master section being amended."
                ),
            }
        )

    penalty = sum(25 if c["severity"] == "CRITICAL" else 15 if c["severity"] == "HIGH" else 8 for c in conflicts)
    alignment_score = round(max(10.0, 100.0 - penalty), 1)

    return {
        "deal_alignment_score": alignment_score,
        "contract_count": len(contracts),
        "conflicts": conflicts,
        "summary": (
            f"Audited {len(contracts)} deal room agreements; identified {len(conflicts)} cross-contract "
            f"contradiction(s) with an overall alignment score of {alignment_score}%."
        ),
    }
