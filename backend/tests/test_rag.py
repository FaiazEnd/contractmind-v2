"""Tests for Contextual RAG chunking, similarity search, and contract index purging."""

from __future__ import annotations

from app.services.rag_engine import RAGEngine


def test_rag_chunking_overlap_and_metadata_prefix() -> None:
    engine = RAGEngine()
    long_text = " ".join(f"clauseword{i}" for i in range(250))
    sections = [
        {
            "section_number": "4.2",
            "title": "Data Processing",
            "text": long_text,
            "page_number": 2,
        }
    ]
    chunks = engine.chunk_sections(sections)
    assert len(chunks) >= 2
    assert chunks[0]["text"].startswith("[Section 4.2: Data Processing] ")
    # Verify 100-char overlap continuity between consecutive chunks
    body_0 = chunks[0]["text"].split("] ", 1)[1]
    body_1 = chunks[1]["text"].split("] ", 1)[1]
    assert body_0[-40:] in body_1 or body_1[:40] in body_0


def test_rag_index_query_and_delete_purge() -> None:
    engine = RAGEngine()
    cid = "test-rag-contract-001"
    sections = [
        {
            "section_number": "2",
            "title": "Indemnification",
            "text": "Seller provides uncapped indemnification for all intellectual property infringement claims.",
            "page_number": 1,
        },
        {
            "section_number": "5",
            "title": "Governing Law",
            "text": "This Agreement is governed by the laws of the State of Delaware.",
            "page_number": 2,
        },
    ]
    count = engine.index_contract(cid, sections)
    assert count == 2

    hits = engine.query_similar(cid, "uncapped indemnification IP claims", n_results=2)
    assert len(hits) >= 1
    assert hits[0]["section_number"] == "2"

    engine.delete_contract_index(cid)
    hits_after = engine.query_similar(cid, "uncapped indemnification", n_results=2)
    assert hits_after == []
