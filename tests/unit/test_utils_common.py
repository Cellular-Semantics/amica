from __future__ import annotations

import pytest

from amica.utils import ToolingContext, chunk_items


@pytest.mark.unit
def test_chunk_items_even_split() -> None:
    data = ["a", "b", "c", "d"]
    assert chunk_items(data, size=2) == [["a", "b"], ["c", "d"]]


@pytest.mark.unit
def test_chunk_items_handles_remainder() -> None:
    data = ["a", "b", "c"]
    assert chunk_items(data, size=2) == [["a", "b"], ["c"]]


@pytest.mark.unit
def test_tooling_context_defaults() -> None:
    ctx = ToolingContext(workspace="/tmp")
    assert ctx.workspace == "/tmp"
    assert ctx.dry_run is False
