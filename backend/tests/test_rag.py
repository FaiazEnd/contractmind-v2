"""Tests for Contextual RAG chunking, 2,000 SEC EDGAR precedents, and deletion purging."""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.legal_knowledge_base import load_legal_precedents
from app.services.rag_engine import RAGEngine, chunk_section_text


def test_legal_precedents_2000_loaded_with_99_categories() -> None:
    precedents = load_legal_precedents()
    assert len(precedents) == 2000
    categories = {p["category"] for p in precedents}
    assert len(categories) == 99


def test_chunking_window_and_pii_redaction() -> None:
    long_body = ("Liability cap SSN 123-45-6789 applies to commercial claims. " * 25).strip()
    chunks = chunk_section_text("4.2", "Limitation of Liability", long_body)
    assert len(chunks) >= 2
    for ch in chunks:
        assert ch["text"].startswith("[Section 4.2: Limitation of Liability] ")
        assert "123-45-6789" not in ch["text"]
        assert "[REDACTED_SSN]" in ch["text"]


def test_rag_index_query_and_purge() -> None:
    engine = RAGEngine()
    kb_count = engine.index_knowledge_base()
    assert kb_count == 2000

    kb_hits = engine.query_knowledge_base("indemnification liability cap", n_results=2)
    assert len(kb_hits) == 2
    assert kb_hits[0]["source"] == "SEC EDGAR / LexGLUE LEDGAR"

    cid = "test-rag-contract-1"
    indexed = engine.index_contract(
        cid,
        [
            {
                "section_number": "3",
                "title": "AI Data Rights",
                "text": "Provider shall not train machine learning models on Customer Data.",
                "page_number": 1,
            }
        ],
    )
    assert indexed >= 1

    hits = engine.query_similar(cid, "machine learning training", n_results=2)
    assert len(hits) == 1
    assert hits[0]["section_number"] == "3"

    purged = engine.delete_contract_index(cid)
    assert purged is True
    assert engine.query_similar(cid, "machine learning training", n_results=2) == []
