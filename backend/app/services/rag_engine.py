"""Contextual RAG & semantic chunking engine with ChromaDB + in-memory cosine fallback."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from app.config import settings
from app.services.legal_knowledge_base import LEGAL_PRECEDENT_DATASET

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def _term_frequency(tokens: list[str]) -> dict[str, float]:
    counts = Counter(tokens)
    total = float(len(tokens) or 1)
    return {tok: cnt / total for tok, cnt in counts.items()}


def _cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    common = set(vec_a.keys()) & set(vec_b.keys())
    dot = sum(vec_a[k] * vec_b[k] for k in common)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class RAGEngine:
    """Persistent ChromaDB engine with automatic in-memory term-frequency cosine fallback."""

    CHUNK_SIZE = 600
    CHUNK_OVERLAP = 100

    def __init__(self, persist_dir: str | None = None) -> None:
        self.persist_dir = persist_dir or settings.CHROMA_PERSIST_DIR
        self._chroma_client: Any = None
        self._using_chroma = False
        self._memory_store: dict[str, list[dict[str, Any]]] = {}
        self._init_chroma()
        self.index_knowledge_base()

    def _init_chroma(self) -> None:
        try:
            import chromadb  # type: ignore

            self._chroma_client = chromadb.PersistentClient(path=self.persist_dir)
            self._using_chroma = True
        except Exception:
            self._chroma_client = None
            self._using_chroma = False

    @property
    def backend_mode(self) -> str:
        return "chromadb" if self._using_chroma else "in_memory_cosine"

    @staticmethod
    def _collection_name(contract_id: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9_-]", "_", contract_id)
        return f"contract_{safe}"[:63]

    def chunk_sections(self, sections: list[dict[str, Any]], raw_text: str = "") -> list[dict[str, Any]]:
        """Create 600-char sliding chunks (100-char overlap) prepended with section metadata."""
        source_sections = sections or (
            [{"section_number": "1", "title": "Full Agreement", "text": raw_text, "page_number": 1}]
            if raw_text
            else []
        )
        chunks: list[dict[str, Any]] = []
        step = max(1, self.CHUNK_SIZE - self.CHUNK_OVERLAP)

        for sec in source_sections:
            sec_num = str(sec.get("section_number", "1"))
            sec_title = str(sec.get("title", "General"))
            sec_text = (sec.get("text") or "").strip()
            if not sec_text:
                continue

            prefix = f"[Section {sec_num}: {sec_title}] "
            if len(sec_text) <= self.CHUNK_SIZE:
                chunks.append(
                    {
                        "id": f"sec_{sec_num}_0",
                        "text": f"{prefix}{sec_text}",
                        "section_number": sec_num,
                        "title": sec_title,
                        "page_number": int(sec.get("page_number", 1)),
                    }
                )
            else:
                idx = 0
                pos = 0
                while pos < len(sec_text):
                    window = sec_text[pos : pos + self.CHUNK_SIZE].strip()
                    if window:
                        chunks.append(
                            {
                                "id": f"sec_{sec_num}_{idx}",
                                "text": f"{prefix}{window}",
                                "section_number": sec_num,
                                "title": sec_title,
                                "page_number": int(sec.get("page_number", 1)),
                            }
                        )
                    if pos + self.CHUNK_SIZE >= len(sec_text):
                        break
                    pos += step
                    idx += 1

        return chunks

    def index_contract(self, contract_id: str, sections: list[dict[str, Any]], raw_text: str = "") -> int:
        """Chunk and index a contract into ChromaDB or the fallback vector store."""
        chunks = self.chunk_sections(sections, raw_text)
        self.delete_contract_index(contract_id)
        if not chunks:
            return 0

        if self._using_chroma and self._chroma_client is not None:
            try:
                col_name = self._collection_name(contract_id)
                collection = self._chroma_client.get_or_create_collection(name=col_name)
                collection.add(
                    ids=[f"{contract_id}_{c['id']}_{i}" for i, c in enumerate(chunks)],
                    documents=[c["text"] for c in chunks],
                    metadatas=[
                        {
                            "contract_id": contract_id,
                            "section_number": c["section_number"],
                            "title": c["title"],
                            "page_number": c["page_number"],
                        }
                        for c in chunks
                    ],
                )
                return len(chunks)
            except Exception:
                # Graceful runtime fallback if Chroma fails during embedding/persistence
                self._using_chroma = False

        # In-memory TF cosine store
        stored = []
        for c in chunks:
            tokens = _tokenize(c["text"])
            stored.append(
                {
                    **c,
                    "vector": _term_frequency(tokens),
                }
            )
        self._memory_store[contract_id] = stored
        return len(stored)

    def query_similar(self, contract_id: str, query: str, n_results: int = 4) -> list[dict[str, Any]]:
        """Return top-N matching contextual passages for a contract."""
        if not query.strip():
            return []

        if self._using_chroma and self._chroma_client is not None:
            try:
                col_name = self._collection_name(contract_id)
                collection = self._chroma_client.get_collection(name=col_name)
                count = collection.count()
                if count == 0:
                    return []
                res = collection.query(query_texts=[query], n_results=min(n_results, count))
                docs = (res.get("documents") or [[]])[0]
                metas = (res.get("metadatas") or [[]])[0]
                dists = (res.get("distances") or [[]])[0]
                results = []
                for doc, meta, dist in zip(docs, metas, dists):
                    results.append(
                        {
                            "text": doc,
                            "section_number": str((meta or {}).get("section_number", "1")),
                            "title": str((meta or {}).get("title", "General")),
                            "score": round(max(0.0, 1.0 - float(dist)), 4),
                        }
                    )
                return results
            except Exception:
                pass

        entries = self._memory_store.get(contract_id, [])
        if not entries:
            return []

        q_vec = _term_frequency(_tokenize(query))
        scored = []
        for entry in entries:
            score = _cosine_similarity(q_vec, entry["vector"])
            scored.append(
                {
                    "text": entry["text"],
                    "section_number": entry["section_number"],
                    "title": entry["title"],
                    "score": round(score, 4),
                }
            )
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:n_results]

    def delete_contract_index(self, contract_id: str) -> None:
        """Purge ChromaDB collection and in-memory vectors for a contract."""
        self._memory_store.pop(contract_id, None)
        if self._chroma_client is not None:
            try:
                col_name = self._collection_name(contract_id)
                self._chroma_client.delete_collection(name=col_name)
            except Exception:
                pass

    def index_knowledge_base(self) -> int:
        """Index the curated external CUAD-style legal precedent dataset into a shared RAG store."""
        kb_id = "__external_knowledge_base__"
        entries: list[dict[str, Any]] = []
        for item in LEGAL_PRECEDENT_DATASET:
            full_text = (
                f"[{item['source']} — {item['category']}] "
                f"Risk: {item['risk_pattern']} "
                f"Market Standard Fallback: {item['market_standard_fallback']} "
                f"Guidance: {item['guidance']}"
            )
            entries.append(
                {
                    "id": item["id"],
                    "text": full_text,
                    "section_number": item["category"],
                    "title": item["source"],
                    "page_number": 1,
                }
            )

        if self._using_chroma and self._chroma_client is not None:
            try:
                collection = self._chroma_client.get_or_create_collection(name="legal_knowledge_base")
                if collection.count() == 0:
                    collection.add(
                        ids=[e["id"] for e in entries],
                        documents=[e["text"] for e in entries],
                        metadatas=[
                            {"source": e["title"], "category": e["section_number"]}
                            for e in entries
                        ],
                    )
                return len(entries)
            except Exception:
                self._using_chroma = False

        self._memory_store[kb_id] = [
            {**e, "vector": _term_frequency(_tokenize(e["text"]))}
            for e in entries
        ]
        return len(entries)

    def query_knowledge_base(self, query: str, n_results: int = 2) -> list[dict[str, Any]]:
        """Retrieve top matching external legal precedents & market-standard fallbacks."""
        if not query.strip():
            return []

        if self._using_chroma and self._chroma_client is not None:
            try:
                collection = self._chroma_client.get_collection(name="legal_knowledge_base")
                count = collection.count()
                if count > 0:
                    res = collection.query(query_texts=[query], n_results=min(n_results, count))
                    docs = (res.get("documents") or [[]])[0]
                    metas = (res.get("metadatas") or [[]])[0]
                    dists = (res.get("distances") or [[]])[0]
                    return [
                        {
                            "text": doc,
                            "category": str((meta or {}).get("category", "Precedent")),
                            "source": str((meta or {}).get("source", "External KB")),
                            "score": round(max(0.0, 1.0 - float(dist)), 4),
                        }
                        for doc, meta, dist in zip(docs, metas, dists)
                    ]
            except Exception:
                pass

        entries = self._memory_store.get("__external_knowledge_base__", [])
        if not entries:
            self.index_knowledge_base()
            entries = self._memory_store.get("__external_knowledge_base__", [])

        q_vec = _term_frequency(_tokenize(query))
        scored = [
            {
                "text": entry["text"],
                "category": entry["section_number"],
                "source": entry["title"],
                "score": round(_cosine_similarity(q_vec, entry["vector"]), 4),
            }
            for entry in entries
        ]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:n_results]


rag_engine = RAGEngine()
