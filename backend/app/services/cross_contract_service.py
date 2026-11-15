"""Deal Room Cross-Contract Contradiction & Precedence Analyzer."""

from __future__ import annotations

import re
import uuid
from typing import Any


_GOVERNING_LAW_RE = re.compile(
    r"(?:governed by|laws of(?: the State of)?|jurisdiction of)\s+(?:the\s+)?(Delaware|New York|California|Texas|England and Wales|United Kingdom|Singapore|Massachusetts|Illinois)",
    re.IGNORECASE,
)

_LIABILITY_CAP_RE = re.compile(
    r"(?:aggregate liability[^.]{0,180}?(?:shall not exceed|capped at|limited to)\s+([^.;]+)|(?:unlimited|uncapped)\s+(?:liability|indemnification)[^.;]*)",
    re.IGNORECASE,
)

_TERMINATION_WINDOW_RE = re.compile(
    r"(?:(\d+)\s*(?:calendar\s+|business\s+)?days(?:\s+prior)?\s*(?:written\s+)?(?:notice|cure)|terminate immediately without (?:notice|cure))",
    re.IGNORECASE,
)

_PRECEDENCE_RE = re.compile(
    r"(?:order of precedence|in the event of (?:a )?conflict[^.]*\.)",
    re.IGNORECASE,
)


def _extract_snippet(text: str, match: re.Match[str], radius: int = 90) -> str:
    start = max(0, match.start() - radius // 2)
    end = min(len(text), match.end() + radius)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def analyze_deal_room_conflicts(contracts: list[Any]) -> dict[str, Any]:
    """Detect contradictions across interrelated agreements (MSA, SOW, DPA, M&A, NDA)."""
    contracts_meta = [
        {
            "id": str(c.id),
            "title": str(c.title),
            "playbook_name": str(c.playbook_name),
            "risk_score": float(c.overall_risk_score or 0.0),
        }
        for c in contracts
    ]

    conflicts: list[dict[str, Any]] = []

    # 1. Governing Law / Jurisdiction Traps
    laws_found: list[dict[str, str]] = []
    for c in contracts:
        text = c.raw_text or ""
        m = _GOVERNING_LAW_RE.search(text)
        if m:
            laws_found.append(
                {
                    "contract_id": str(c.id),
                    "title": str(c.title),
                    "jurisdiction": m.group(1).strip().title(),
                    "excerpt": _extract_snippet(text, m),
                }
            )

    distinct_laws = {item["jurisdiction"] for item in laws_found}
    if len(distinct_laws) > 1:
        conflicts.append(
            {
                "id": str(uuid.uuid4())[:8],
                "category": "Governing Law & Venue Trap",
                "severity": "HIGH",
                "title": f"Conflicting Governing Jurisdictions ({', '.join(sorted(distinct_laws))})",
                "description": "Related deal documents specify incompatible governing laws and dispute venues, creating forum-shopping and enforceability risk during cross-agreement disputes.",
                "precedence_risk": "Without a harmonized governing law override, a breach spanning both agreements triggers parallel litigation in conflicting jurisdictions.",
                "affected_contracts": [item["title"] for item in laws_found],
                "conflicting_excerpts": [
                    {"contract": item["title"], "value": item["jurisdiction"], "excerpt": item["excerpt"]}
                    for item in laws_found
                ],
                "harmonization_clause": "All ancillary schedules, SOWs, and DPAs shall be governed exclusively by the laws of the State of Delaware, and Section 12 of the Master Agreement controls over any conflicting venue clause.",
            }
        )

    # 2. Limitation of Liability Cap Discrepancies
    caps_found: list[dict[str, str]] = []
    for c in contracts:
        text = c.raw_text or ""
        m = _LIABILITY_CAP_RE.search(text)
        if m:
            val = (m.group(1) or m.group(0)).strip()
            caps_found.append(
                {
                    "contract_id": str(c.id),
                    "title": str(c.title),
                    "cap_value": val[:100],
                    "excerpt": _extract_snippet(text, m),
                }
            )

    if len(caps_found) >= 2:
        normalized_caps = {re.sub(r"\s+", " ", item["cap_value"].lower()) for item in caps_found}
        has_uncapped = any("unlimited" in item["cap_value"].lower() or "uncapped" in item["cap_value"].lower() for item in caps_found)
        if len(normalized_caps) > 1 or has_uncapped:
            conflicts.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "category": "Liability Cap Contradiction",
                    "severity": "CRITICAL" if has_uncapped else "HIGH",
                    "title": "Divergent Limitation of Liability Caps Across Deal Documents",
                    "description": "Liability ceilings differ across selected agreements (including uncapped carve-outs or mismatched fee-multiplier caps).",
                    "precedence_risk": "A plaintiff may claim under whichever instrument offers the higher or uncapped liability ceiling, bypassing the Master Agreement cap.",
                    "affected_contracts": [item["title"] for item in caps_found],
                    "conflicting_excerpts": [
                        {"contract": item["title"], "value": item["cap_value"], "excerpt": item["excerpt"]}
                        for item in caps_found
                    ],
                    "harmonization_clause": "Notwithstanding anything to the contrary in any SOW, DPA, or Schedule, each party's aggregate cumulative liability across all Deal Documents shall not exceed twelve (12) months of fees paid under the Master Agreement (with a 2x super-cap solely for confirmed data breaches).",
                }
            )

    # 3. Termination Notice & Cure Window Asymmetry
    term_windows: list[dict[str, str]] = []
    for c in contracts:
        text = c.raw_text or ""
        m = _TERMINATION_WINDOW_RE.search(text)
        if m:
            val = f"{m.group(1)} days" if m.group(1) else "Immediate (0-day cure)"
            term_windows.append(
                {
                    "contract_id": str(c.id),
                    "title": str(c.title),
                    "window": val,
                    "excerpt": _extract_snippet(text, m),
                }
            )

    if len({item["window"] for item in term_windows}) > 1:
        conflicts.append(
            {
                "id": str(uuid.uuid4())[:8],
                "category": "Termination & Cure Asymmetry",
                "severity": "HIGH",
                "title": "Asymmetric Cure & Termination Notice Windows",
                "description": "Selected contracts establish mismatched cure periods or immediate termination triggers that destabilize dependent obligations.",
                "precedence_risk": "Termination of an underlying DPA or SaaS schedule with a 0-day cure window can leave the MSA payment stream active while services cease.",
                "affected_contracts": [item["title"] for item in term_windows],
                "conflicting_excerpts": [
                    {"contract": item["title"], "value": item["window"], "excerpt": item["excerpt"]}
                    for item in term_windows
                ],
                "harmonization_clause": "Termination for material breach under any Deal Document requires thirty (30) days prior written notice and opportunity to cure; termination of the Master Agreement shall co-terminate all dependent SOWs and Schedules.",
            }
        )

    # 4. Order of Precedence & AI/Data Policy Conflict
    prec_docs = []
    ai_train_docs = []
    ai_ban_docs = []
    for c in contracts:
        text = c.raw_text or ""
        if _PRECEDENCE_RE.search(text):
            prec_docs.append(c.title)
        lower = text.lower()
        if any(k in lower for k in ("train machine learning", "train ai", "train its proprietary")):
            ai_train_docs.append(c.title)
        if any(k in lower for k in ("shall not train", "prohibit", "never use customer data to train", "strictly prohibited")):
            ai_ban_docs.append(c.title)

    if ai_train_docs and ai_ban_docs:
        conflicts.append(
            {
                "id": str(uuid.uuid4())[:8],
                "category": "Data & AI Governance Conflict",
                "severity": "CRITICAL",
                "title": "AI Model Training Permission vs. DPA Prohibition",
                "description": f"{', '.join(ai_train_docs)} permits AI/ML model training on Customer Data while {', '.join(ai_ban_docs)} prohibits secondary AI training.",
                "precedence_risk": "Conflicting data-usage grants create immediate GDPR/CCPA compliance exposure and nullify enterprise AI guardrails.",
                "affected_contracts": list(dict.fromkeys(ai_train_docs + ai_ban_docs)),
                "conflicting_excerpts": [
                    {"contract": t, "value": "Permits AI Training", "excerpt": "Grants license to train AI/ML models on telemetry or inputs."}
                    for t in ai_train_docs
                ]
                + [
                    {"contract": t, "value": "Prohibits AI Training", "excerpt": "Restricts processing strictly to service delivery."}
                    for t in ai_ban_docs
                ],
                "harmonization_clause": "The Data Processing Addendum's prohibition on AI/ML model training shall strictly supersede any broader data license or service-improvement clause in the MSA, SaaS Agreement, or Order Form.",
            }
        )
    elif len(prec_docs) < len(contracts):
        conflicts.append(
            {
                "id": str(uuid.uuid4())[:8],
                "category": "Order of Precedence Gap",
                "severity": "MEDIUM",
                "title": "Missing Harmonized Order-of-Precedence Hierarchy",
                "description": "Not all agreements in this Deal Room define an explicit order of precedence when commercial schedules conflict with master terms.",
                "precedence_risk": "Later-dated SOWs or click-through terms may inadvertently override negotiated MSA protections.",
                "affected_contracts": [c.title for c in contracts],
                "conflicting_excerpts": [
                    {"contract": c.title, "value": "Has Precedence Clause" if c.title in prec_docs else "No Explicit Precedence", "excerpt": "Hierarchy ambiguity across multi-document stack."}
                    for c in contracts
                ],
                "harmonization_clause": "Order of Precedence: (1) Data Processing Addendum (for data protection), (2) Master Services Agreement, (3) Executed SOWs (solely as to scope and pricing), and (4) Vendor Policies.",
            }
        )

    # Compute Deal Alignment Score (0-100%)
    penalty = 0.0
    for conf in conflicts:
        sev = conf["severity"]
        if sev == "CRITICAL":
            penalty += 28.0
        elif sev == "HIGH":
            penalty += 18.0
        else:
            penalty += 10.0

    deal_alignment_score = round(max(12.0, 100.0 - penalty), 1)
    summary = (
        f"Audited {len(contracts)} interrelated agreements and detected {len(conflicts)} cross-contract contradiction(s). "
        + (
            "Immediate harmonization of liability caps and governing law is recommended prior to execution."
            if conflicts
            else "All selected agreements are aligned across core commercial and legal terms."
        )
    )

    return {
        "deal_alignment_score": deal_alignment_score,
        "contracts_analyzed": contracts_meta,
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "summary": summary,
    }
