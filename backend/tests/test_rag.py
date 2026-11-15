"""Tests for Contextual RAG chunking, similarity query, and index deletion."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.rag_engine import RAGEngine, chunk_section


def test_chunk_section_sliding_window():
    long_text = "Confidentiality obligation clause. " * 40  # > 1200 chars
    chunks = chunk_section("4", "Confidentiality", long_text, page_number=2, chunk_size=600, overlap=100)
    assert len(chunks) >= 2
    assert all(c["text"].startswith("[Section 4: Confidentiality]") for c in chunks)


def test_rag_index_query_and_purge(tmp_path):
    engine = RAGEngine(persist_dir=str(tmp_path / "chroma"))
    sections = [
        {
            "section_number": "3",
            "title": "Indemnification",
            "text": "Customer shall indemnify Provider from third-party intellectual property infringement claims.",
            "page_number": 1,
        },
        {
            "section_number": "7",
            "title": "Payment Terms",
            "text": "Customer shall remit subscription fees Net 30 days from receipt of valid invoice.",
            "page_number": 2,
        },
    ]
    count = engine.index_contract("c-rag-1", sections)
    assert count == 2

    hits = engine.query_similar("c-rag-1", "indemnity intellectual property", n_results=2)
    assert len(hits) >= 1
    assert hits[0]["section_number"] == "3"

    engine.delete_contract_index("c-rag-1")
    after_purge = engine.query_similar("c-rag-1", "indemnity", n_results=2)
    assert after_purge == []
