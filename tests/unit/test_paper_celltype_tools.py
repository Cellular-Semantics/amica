from __future__ import annotations

import pytest

from amica.agents.paper_celltype import paper_celltype_tools as tools
from amica.services.vector_store import DocumentChunk


pytestmark = pytest.mark.unit


class DummyVectorStore:
    def similarity_search(self, doi: str, query: str, top_k: int = 3):
        return [
            DocumentChunk(index=0, start=0, end=10, text="Alpha chunk", embedding=[1.0])
        ]


def test_search_cached_snippets_returns_text(monkeypatch):
    monkeypatch.setattr(tools, "_get_vector_store", lambda: DummyVectorStore())
    result = tools.search_cached_snippets(None, "DOI:1", "alpha", top_k=1)
    assert result == ["Alpha chunk"]


def test_search_cached_snippets_handles_missing_store(monkeypatch):
    monkeypatch.setattr(tools, "_get_vector_store", lambda: None)
    assert tools.search_cached_snippets(None, "DOI:1", "alpha") == []
