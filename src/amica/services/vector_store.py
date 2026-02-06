"""Lightweight document chunking and embedding utilities for CXG workflows."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import sqrt
import json
import logging
from pathlib import Path
from typing import Protocol, Sequence

from amica.utils.cxg import CxgResourceLayout, normalise_identifier

logger = logging.getLogger(__name__)


class EmbeddingBackend(Protocol):
    """Protocol implemented by backends that can embed batches of text chunks."""

    model_name: str

    def embed(
        self,
        chunks: Sequence[str],
        *,
        metadata: dict[str, str] | None = None,
    ) -> list[list[float]]:
        """Return embedding vectors for every chunk in ``chunks``."""


class OpenAIEmbeddingBackend:
    """Embedding backend that delegates to the OpenAI embeddings API."""

    def __init__(self, *, model_name: str) -> None:
        from openai import OpenAI  # lazy import to avoid hard dependency in tests

        self.model_name = model_name
        self._client = OpenAI()

    def embed(
        self,
        chunks: Sequence[str],
        *,
        metadata: dict[str, str] | None = None,
    ) -> list[list[float]]:
        if not chunks:
            return []
        response = self._client.embeddings.create(
            model=self.model_name, input=list(chunks)
        )
        usage = getattr(response, "usage", None)
        if usage:
            if hasattr(usage, "model_dump"):
                usage_payload = usage.model_dump()
            elif hasattr(usage, "to_dict"):
                usage_payload = usage.to_dict()
            else:
                usage_payload = usage
            payload = {
                "kind": "embedding",
                "model": self.model_name,
                "chunks": len(chunks),
                "metadata": metadata or {},
                "usage": usage_payload,
            }
            logger.info("openai_usage %s", json.dumps(payload))
        # OpenAI preserves ordering of supplied inputs
        return [record.embedding for record in response.data]


@dataclass(slots=True)
class DocumentChunk:
    """Serializable representation of a chunk of an article."""

    index: int
    start: int
    end: int
    text: str
    embedding: list[float]


class DocumentVectorStore:
    """Persisted storage for chunked article embeddings."""

    def __init__(
        self,
        layout: CxgResourceLayout,
        *,
        backend: EmbeddingBackend,
        chunk_chars: int = 1200,
        chunk_overlap: int = 200,
    ) -> None:
        if chunk_overlap >= chunk_chars:
            raise ValueError("chunk_overlap must be smaller than chunk_chars")
        self.layout = layout
        self.backend = backend
        self.chunk_chars = chunk_chars
        self.chunk_overlap = chunk_overlap
        self._index_dir = self.layout.cache_dir / "vector_store"
        self._index_dir.mkdir(parents=True, exist_ok=True)

    def ensure_index(self, article_id: str, article_text: str) -> list[DocumentChunk]:
        """Return cached chunks for ``article_id``, creating them if missing."""

        slug = normalise_identifier(article_id or "unknown")
        payload_path = self._index_dir / f"{slug}_{self.backend.model_name}.json"
        if payload_path.exists():
            return self._read_payload(payload_path)

        chunks_with_offsets = list(self._chunk_text(article_text))
        texts = [chunk for chunk, _, _ in chunks_with_offsets]
        embeddings = self.backend.embed(
            texts,
            metadata={"article_id": article_id, "phase": "index"},
        )
        if len(embeddings) != len(texts):
            raise RuntimeError(
                "Embedding backend returned mismatched vector count: "
                f"expected {len(texts)}, got {len(embeddings)}"
            )

        document_chunks = [
            DocumentChunk(
                index=idx,
                start=start,
                end=end,
                text=text,
                embedding=emb,
            )
            for idx, ((text, start, end), emb) in enumerate(
                zip(chunks_with_offsets, embeddings, strict=True)
            )
        ]

        payload = {
            "article_id": article_id,
            "model": self.backend.model_name,
            "chunks": [asdict(chunk) for chunk in document_chunks],
        }
        payload_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.debug(
            "Indexed %s chunks for article %s", len(document_chunks), article_id
        )
        return document_chunks

    def load_index(self, article_id: str) -> list[DocumentChunk]:
        """Return chunks for ``article_id`` if an index exists, else an empty list."""

        slug = normalise_identifier(article_id or "unknown")
        payload_path = self._index_dir / f"{slug}_{self.backend.model_name}.json"
        if not payload_path.exists():
            return []
        return self._read_payload(payload_path)

    def similarity_search(
        self,
        article_id: str,
        query: str,
        *,
        top_k: int = 3,
    ) -> list[DocumentChunk]:
        """Return top ``top_k`` chunks ranked by cosine similarity to ``query``."""

        chunks = self.load_index(article_id)
        if not chunks or not query.strip():
            return []

        query_embedding = self.backend.embed(
            [query],
            metadata={"article_id": article_id, "phase": "query"},
        )
        if not query_embedding:
            return []
        query_vector = query_embedding[0]

        scored: list[tuple[float, DocumentChunk]] = []
        for chunk in chunks:
            similarity = _cosine_similarity(query_vector, chunk.embedding)
            scored.append((similarity, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for score, chunk in scored[:top_k] if score > 0]

    def _read_payload(self, path: Path) -> list[DocumentChunk]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        chunks = payload.get("chunks", [])
        return [DocumentChunk(**chunk) for chunk in chunks]

    def _chunk_text(self, text: str) -> list[tuple[str, int, int]]:
        if not text:
            return []
        cleaned = text.replace("\r\n", "\n")
        max_len = self.chunk_chars
        overlap = self.chunk_overlap
        pos = 0
        chunks: list[tuple[str, int, int]] = []
        text_length = len(cleaned)
        while pos < text_length:
            end = min(text_length, pos + max_len)
            chunk = cleaned[pos:end].strip()
            if chunk:
                chunks.append((chunk, pos, end))
            if end == text_length:
                break
            pos = max(0, end - overlap)
            if pos >= text_length:
                break
        return chunks


__all__ = [
    "DocumentChunk",
    "DocumentVectorStore",
    "EmbeddingBackend",
    "OpenAIEmbeddingBackend",
]


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sqrt(sum(x * x for x in a))
    norm_b = sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
