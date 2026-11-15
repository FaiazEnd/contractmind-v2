"""Contextual RAG & semantic chunking engine with ChromaDB + TF cosine fallback."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional

from app.config import settings

try:
    import chromadb
except ImportError:  # pragma: no cover
    chromadb = None  # type: ignore[assignment]


_WORD_RE = re.compile(r"[a-zA-Z0-9_]+")


def _tokenize_terms(text: str) -> Counter[str]:
    return Counter(w.lower() for w in _WORD_RE.findall(text))


def _cosine_similarity(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    common = set(a.keys()) & set(b.keys())
    dot = sum(a[k] * b[k] for k in common)
    if dot == 0:
        return 0.0
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def chunk_section(
    section_number: str,
    title: str,
    text: str,
    page_number: int = 1,
    chunk_size: int = 600,
    overlap: int = 100,
) -> List[Dict[str, Any]]:
    """Split a section into sliding 600-char windows with 100-char overlap and contextual header."""
    cleaned = (text or "").strip()
    if not cleaned:
        return []

    step = max(1, chunk_size - overlap)
    chunks: List[Dict[str, Any]] = []
    start = 0
    idx = 0
    while start < len(cleaned):
        window = cleaned[start : start + chunk_size].strip()
        if window:
            contextual_text = f"[Section {section_number}: {title}] {window}"
            chunks.append(
                {
                    "chunk_id": f"sec_{section_number}_{idx}",
                    "section_number": str(section_number),
                    "title": title,
                    "page_number": page_number,
                    "text": contextual_text,
                }
            )
            idx += 1
        if start + chunk_size >= len(cleaned):
            break
        start += step
    return chunks


class RAGEngine:
    """Contextual RAG engine backed by ChromaDB PersistentClient with in-memory fallback."""

    def __init__(self, persist_dir: Optional[str] = None) -> None:
        self.persist_dir = persist_dir or settings.CHROMA_PERSIST_DIR
        self._memory_store: Dict[str, List[Dict[str, Any]]] = {}
        self._client = None
        self.backend_mode = "memory_cosine"

        if chromadb is not None:
            try:
                self._client = chromadb.PersistentClient(path=self.persist_dir)
                self.backend_mode = "chromadb"
            except Exception:
                self._client = None
                self.backend_mode = "memory_cosine"

    @staticmethod
    def _collection_name(contract_id: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9_-]", "_", contract_id)
        return f"contract_{safe}"[:63]

    def index_contract(self, contract_id: str, sections: List[Dict[str, Any]]) -> int:
        """Chunk and index all contract sections into ChromaDB or fallback vector store."""
        all_chunks: List[Dict[str, Any]] = []
        for idx, sec in enumerate(sections):
            sec_num = str(sec.get("section_number", idx + 1))
            sec_title = str(sec.get("title", f"Section {sec_num}"))
            sec_text = str(sec.get("text", ""))
            sec_page = int(sec.get("page_number", 1))
            sec_chunks = chunk_section(sec_num, sec_title, sec_text, page_number=sec_page)
            # Ensure globally unique chunk ids across sections
            for c_i, c in enumerate(sec_chunks):
                c["chunk_id"] = f"{contract_id}_{idx}_{c_i}"
            all_chunks.extend(sec_chunks)

        # Always keep memory store synced for instant fallback and fast keyword scoring
        self._memory_store[contract_id] = [
            {**c, "tf": _tokenize_terms(c["text"])} for c in all_chunks
        ]

        if self._client is not None and all_chunks:
            col_name = self._collection_name(contract_id)
            try:
                try:
                    self._client.delete_collection(name=col_name)
                except Exception:
                    pass
                collection = self._client.get_or_create_collection(name=col_name)
                collection.add(
                    ids=[c["chunk_id"] for c in all_chunks],
                    documents=[c["text"] for c in all_chunks],
                    metadatas=[
                        {
                            "contract_id": contract_id,
                            "section_number": c["section_number"],
                            "title": c["title"],
                            "page_number": c["page_number"],
                        }
                        for c in all_chunks
                    ],
                )
            except Exception:
                # Fallback silently to in-memory cosine store if Chroma embedding download/runtime fails
                pass

        return len(all_chunks)

    def query_similar(
        self,
        contract_id: str,
        query: str,
        n_results: int = 4,
        fallback_sections: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve top matching contextual passages for a contract query."""
        if contract_id not in self._memory_store and fallback_sections:
            self.index_contract(contract_id, fallback_sections)

        if self._client is not None:
            col_name = self._collection_name(contract_id)
            try:
                collection = self._client.get_collection(name=col_name)
                count = collection.count()
                if count > 0:
                    res = collection.query(
                        query_texts=[query],
                        n_results=min(n_results, count),
                    )
                    docs = (res.get("documents") or [[]])[0]
                    metas = (res.get("metadatas") or [[]])[0]
                    dists = (res.get("distances") or [[]])[0]
                    results: List[Dict[str, Any]] = []
                    for i, doc in enumerate(docs):
                        meta = metas[i] if i < len(metas) else {}
                        dist = float(dists[i]) if i < len(dists) else 0.5
                        score = round(max(0.0, 1.0 / (1.0 + dist)), 4)
                        results.append(
                            {
                                "section_number": meta.get("section_number", "1"),
                                "title": meta.get("title", "Clause"),
                                "page_number": meta.get("page_number", 1),
                                "text": doc,
                                "score": score,
                            }
                        )
                    if results:
                        return results
            except Exception:
                pass

        # In-memory term-frequency cosine similarity fallback
        entries = self._memory_store.get(contract_id, [])
        if not entries:
            return []

        q_vec = _tokenize_terms(query)
        scored: List[tuple[float, Dict[str, Any]]] = []
        for entry in entries:
            sim = _cosine_similarity(q_vec, entry["tf"])
            scored.append((sim, entry))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                "section_number": item["section_number"],
                "title": item["title"],
                "page_number": item["page_number"],
                "text": item["text"],
                "score": round(score, 4),
            }
            for score, item in scored[:n_results]
        ]

    def delete_contract_index(self, contract_id: str) -> None:
        """Purge ChromaDB collection and in-memory index for a deleted contract."""
        self._memory_store.pop(contract_id, None)
        if self._client is not None:
            col_name = self._collection_name(contract_id)
            try:
                self._client.delete_collection(name=col_name)
            except Exception:
                pass


rag_engine = RAGEngine()
