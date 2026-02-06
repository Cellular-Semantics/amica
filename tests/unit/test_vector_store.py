from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from amica.services.vector_store import DocumentVectorStore
from amica.utils.cxg import CxgResourceLayout


pytestmark = pytest.mark.unit


@dataclass
class DummyEmbeddingBackend:
    model_name: str = "dummy"
    calls: int = 0

    def embed(
        self,
        chunks: list[str],
        *,
        metadata: dict[str, str] | None = None,
    ) -> list[list[float]]:  # type: ignore[override]
        self.calls += 1
        return [[float(len(chunk))] for chunk in chunks]


@dataclass
class KeywordEmbeddingBackend:
    model_name: str = "keyword"
    calls: int = 0
    history: list[list[str]] = field(default_factory=list)

    def embed(
        self,
        chunks: list[str],
        *,
        metadata: dict[str, str] | None = None,
    ) -> list[list[float]]:  # type: ignore[override]
        self.calls += 1
        self.history.append(list(chunks))
        vectors: list[list[float]] = []
        for chunk in chunks:
            if "alpha" in chunk.lower():
                vectors.append([1.0, 0.0])
            elif "beta" in chunk.lower():
                vectors.append([0.0, 1.0])
            else:
                vectors.append([1.0, 1.0])
        return vectors


@pytest.fixture
def layout(tmp_path):
    resources = tmp_path / "cxg"
    layout = CxgResourceLayout(resources_dir=resources)
    layout.ensure_directories()
    return layout


def test_chunking_and_persistence(layout):
    backend = DummyEmbeddingBackend()
    store = DocumentVectorStore(
        layout, backend=backend, chunk_chars=20, chunk_overlap=5
    )

    article_text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit."
    chunks_first = store.ensure_index("DOI:123", article_text)

    assert len(chunks_first) >= 2
    assert backend.calls == 1

    # Invoking ensure_index again should reuse cached payload and skip embeddings
    chunks_second = store.ensure_index("DOI:123", article_text)
    assert [chunk.text for chunk in chunks_second] == [
        chunk.text for chunk in chunks_first
    ]
    assert backend.calls == 1


def test_similarity_search_returns_ranked_chunks(layout):
    backend = KeywordEmbeddingBackend()
    store = DocumentVectorStore(
        layout, backend=backend, chunk_chars=15, chunk_overlap=2
    )

    article_text = "Alpha neurons regulate signals. Beta glia provide support."
    store.ensure_index("DOI:ABC", article_text)

    results = store.similarity_search("DOI:ABC", "alpha investigation", top_k=1)
    assert len(results) == 1
    assert "Alpha" in results[0].text
