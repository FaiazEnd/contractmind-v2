"""External Legal Clause & Precedent Knowledge Base (2,000 CUAD, EDGAR, GDPR, HIPAA, SOC 2 & SaaS Precedents)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_JSON_PATH = Path(__file__).resolve().parent / "legal_precedents_2000.json"

with _JSON_PATH.open("r", encoding="utf-8") as _f:
    LEGAL_PRECEDENT_DATASET: list[dict[str, Any]] = json.load(_f)
