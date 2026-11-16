"""Contextual RAG & SEC EDGAR Precedent Engine with ChromaDB + cosine fallback."""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from app.config import settings
from app.services.legal_knowledge_base import load_legal_precedents
from app.services.pdf_processor import redact_pii


WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize_terms(text: str) -> Counter[str]:
    return Counter(WORD_RE.findall((text or "").lower()))


def _cosine_similarity(vec_a: Counter[str], vec_b: Counter[str]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    common = set(vec_a.keys()) & set(vec_b.keys())
    if not common:
        return 0.0
    dot = sum(vec_a[k] * vec_b[k] for k in common)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def chunk_section_text(
    section_number: str,
    title: str,
    text: str,
    chunk_size: int = 600,
    overlap: int = 100,
) -> list[dict[str, Any]]:
    """Slide a 600-character window with 100-character overlap and prepend section metadata."""
    clean_text = redact_pii(text or "").strip()
    if not clean_text:
        return []

    step = max(1, chunk_size - overlap)
    chunks: list[dict[str, Any]] = []
    start = 0
    idx = 0
    while start < len(clean_text):
        piece = clean_text[start : start + chunk_size].strip()
        if piece:
            tagged = f"[Section {section_number}: {title}] {piece}"
            chunks.append(
                {
                    "chunk_index": idx,
                    "section_number": str(section_number),
                    "title": title,
                    "text": tagged,
                }
            )
            idx += 1
        if start + chunk_size >= len(clean_text):
            break
        start += step
    return chunks


class RAGEngine:
    """Persistent ChromaDB vector engine with automatic in-memory cosine fallback."""

    def __init__(self) -> None:
        self._chroma_client: Any = None
        self._use_chroma = False
        self._memory_collections: dict[str, list[dict[str, Any]]] = {}
        self._kb_indexed = False
        self._init_backend()

    def _init_backend(self) -> None:
        try:
            import chromadb  # type: ignore

            self._chroma_client = chromadb.PersistentClient(
                path=settings.CHROMA_PERSIST_DIR
            )
            self._use_chroma = True
        except Exception:
            self._chroma_client = None
            self._use_chroma = False

    @property
    def backend_name(self) -> str:
        return "chromadb" if self._use_chroma else "in-memory-cosine"

    def _collection_name(self, contract_id: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9_-]", "_", contract_id)
        return f"contract_{safe}"[:63]

    def index_contract(
        self, contract_id: str, sections: list[dict[str, Any]]
    ) -> int:
        """Chunk sections (600 chars / 100 overlap), redact PII, and index into vector store."""
        all_chunks: list[dict[str, Any]] = []
        for sec in sections:
            sec_num = str(sec.get("section_number", "1"))
            sec_title = str(sec.get("title", "Clause"))
            sec_text = str(sec.get("text", ""))
            all_chunks.extend(chunk_section_text(sec_num, sec_title, sec_text))

        if not all_chunks:
            return 0

        col_name = self._collection_name(contract_id)

        if self._use_chroma and self._chroma_client is not None:
            try:
                try:
                    self._chroma_client.delete_collection(name=col_name)
                except Exception:
                    pass
                col = self._chroma_client.get_or_create_collection(name=col_name)
                col.add(
                    ids=[f"{contract_id}_{i}" for i in range(len(all_chunks))],
                    documents=[c["text"] for c in all_chunks],
                    metadatas=[
                        {
                            "contract_id": contract_id,
                            "section_number": c["section_number"],
                            "title": c["title"],
                        }
                        for c in all_chunks
                    ],
                )
            except Exception:
                self._use_chroma = False

        # Always keep fast in-memory mirror / fallback synchronized
        self._memory_collections[col_name] = [
            {
                "id": f"{contract_id}_{i}",
                "text": c["text"],
                "metadata": {
                    "contract_id": contract_id,
                    "section_number": c["section_number"],
                    "title": c["title"],
                },
                "tf": _tokenize_terms(c["text"]),
            }
            for i, c in enumerate(all_chunks)
        ]
        return len(all_chunks)

    def query_similar(
        self, contract_id: str, query: str, n_results: int = 4
    ) -> list[dict[str, Any]]:
        """Retrieve top matching contextual passages from the target contract."""
        col_name = self._collection_name(contract_id)
        if self._use_chroma and self._chroma_client is not None:
            try:
                col = self._chroma_client.get_collection(name=col_name)
                res = col.query(query_texts=[query], n_results=n_results)
                docs = (res.get("documents") or [[]])[0]
                metas = (res.get("metadatas") or [[]])[0]
                dists = (res.get("distances") or [[]])[0]
                out = []
                for idx, doc in enumerate(docs):
                    meta = metas[idx] if idx < len(metas) else {}
                    dist = dists[idx] if idx < len(dists) else 0.5
                    out.append(
                        {
                            "text": doc,
                            "section_number": meta.get("section_number", ""),
                            "title": meta.get("title", ""),
                            "score": round(max(0.0, 1.0 - float(dist)), 4),
                        }
                    )
                if out:
                    return out
            except Exception:
                pass

        items = self._memory_collections.get(col_name, [])
        if not items:
            return []
        q_tf = _tokenize_terms(query)
        scored = []
        for item in items:
            sim = _cosine_similarity(q_tf, item["tf"])
            scored.append((sim, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "text": item["text"],
                "section_number": item["metadata"].get("section_number", ""),
                "title": item["metadata"].get("title", ""),
                "score": round(sim, 4),
            }
            for sim, item in scored[:n_results]
        ]

    def delete_contract_index(self, contract_id: str) -> bool:
        """Purge contract embeddings from ChromaDB and in-memory store."""
        col_name = self._collection_name(contract_id)
        removed = False
        if self._use_chroma and self._chroma_client is not None:
            try:
                self._chroma_client.delete_collection(name=col_name)
                removed = True
            except Exception:
                pass
        if col_name in self._memory_collections:
            del self._memory_collections[col_name]
            removed = True
        return removed

    def index_knowledge_base(self) -> int:
        """Load and index all 2,000 SEC EDGAR / LexGLUE LEDGAR legal precedents."""
        if self._kb_indexed and "legal_precedents" in self._memory_collections:
            return len(self._memory_collections["legal_precedents"])

        precedents = load_legal_precedents()
        if not precedents:
            return 0

        if self._use_chroma and self._chroma_client is not None:
            try:
                col = self._chroma_client.get_or_create_collection(
                    name="legal_precedents"
                )
                if col.count() < len(precedents):
                    # Batch add in chunks of 250
                    for start in range(0, len(precedents), 250):
                        batch = precedents[start : start + 250]
                        col.upsert(
                            ids=[p["id"] for p in batch],
                            documents=[p["text"] for p in batch],
                            metadatas=[
                                {
                                    "category": p["category"],
                                    "source": p.get("source", "SEC EDGAR / LexGLUE LEDGAR"),
                                    "risk_orientation": p.get("risk_orientation", ""),
                                }
                                for p in batch
                            ],
                        )
            except Exception:
                self._use_chroma = False

        self._memory_collections["legal_precedents"] = [
            {
                "id": p["id"],
                "text": p["text"],
                "metadata": {
                    "category": p["category"],
                    "source": p.get("source", "SEC EDGAR / LexGLUE LEDGAR"),
                    "risk_orientation": p.get("risk_orientation", ""),
                },
                "tf": _tokenize_terms(f"{p['category']} {p['text']}"),
            }
            for p in precedents
        ]
        self._kb_indexed = True
        return len(precedents)

    def query_knowledge_base(
        self, query: str, n_results: int = 2
    ) -> list[dict[str, Any]]:
        """Retrieve relevant SEC EDGAR / LexGLUE LEDGAR precedent clauses."""
        if not self._kb_indexed:
            self.index_knowledge_base()

        if self._use_chroma and self._chroma_client is not None:
            try:
                col = self._chroma_client.get_collection(name="legal_precedents")
                res = col.query(query_texts=[query], n_results=n_results)
                docs = (res.get("documents") or [[]])[0]
                metas = (res.get("metadatas") or [[]])[0]
                dists = (res.get("distances") or [[]])[0]
                out = []
                for idx, doc in enumerate(docs):
                    meta = metas[idx] if idx < len(metas) else {}
                    dist = dists[idx] if idx < len(dists) else 0.4
                    out.append(
                        {
                            "text": doc,
                            "category": meta.get("category", "General"),
                            "source": meta.get("source", "SEC EDGAR / LexGLUE LEDGAR"),
                            "risk_orientation": meta.get("risk_orientation", ""),
                            "score": round(max(0.0, 1.0 - float(dist)), 4),
                        }
                    )
                if out:
                    return out
            except Exception:
                pass

        items = self._memory_collections.get("legal_precedents", [])
        if not items:
            return []
        q_tf = _tokenize_terms(query)
        scored = []
        for item in items:
            sim = _cosine_similarity(q_tf, item["tf"])
            scored.append((sim, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "text": item["text"],
                "category": item["metadata"].get("category", "General"),
                "source": item["metadata"].get("source", "SEC EDGAR / LexGLUE LEDGAR"),
                "risk_orientation": item["metadata"].get("risk_orientation", ""),
                "score": round(sim, 4),
            }
            for sim, item in scored[:n_results]
        ]


rag_engine = RAGEngine()
