from __future__ import annotations

import pytest

from amica.agents.annotator.annotator_tools import search_cl


class DummyAdapter:
    def basic_search(self, term: str):
        assert term == "astrocyte"
        return ["CL:0000127"]

    def labels(self, results):
        for identifier in results:
            yield (identifier, "astrocyte")


@pytest.mark.unit
def test_search_cl_returns_label(monkeypatch) -> None:
    monkeypatch.setattr(
        "amica.agents.annotator.annotator_tools.get_adapter",
        lambda name: DummyAdapter(),
    )
    matches = search_cl(None, "astrocyte")
    assert matches == [("CL:0000127", "astrocyte")]
