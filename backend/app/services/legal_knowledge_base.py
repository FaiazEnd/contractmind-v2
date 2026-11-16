"""Loader for the 2,000-clause SEC EDGAR / LexGLUE LEDGAR legal precedents corpus."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PRECEDENTS_PATH = Path(__file__).resolve().parent / "legal_precedents_2000.json"


def load_legal_precedents() -> list[dict[str, Any]]:
    """Load the 2,000 commercial contract precedent clauses across 99 LEDGAR categories."""
    if not PRECEDENTS_PATH.exists():
        return []
    with PRECEDENTS_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return []
