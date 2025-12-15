from __future__ import annotations

import asyncio
import json
from pathlib import Path
import logging

import pytest

from amica.services.expansion_service import ExpansionService
from amica.services.vector_store import DocumentVectorStore
from amica.utils.cxg import (
    AnnotationRecord,
    CxgPipelineSettings,
    CxgResourceLayout,
    PreparedAnnotationBundle,
    normalise_identifier,
)


pytestmark = pytest.mark.integration


class DummyAgent:
    def __init__(self, prompts: list[str]) -> None:
        self.prompts = prompts

    async def run(self, prompt: str):  # type: ignore[override]
        self.prompts.append(prompt)

        class _Result:
            def __init__(self) -> None:
                from amica.agents.paper_celltype.paper_celltype_agent import (
                    BiocurationOutput,
                    CellTypeEntry,
                )

                self.output = BiocurationOutput(
                    cell_type_annotations=[
                        CellTypeEntry(name="alpha", full_name="alpha")
                    ]
                )

        return _Result()


class DummyVectorStore(DocumentVectorStore):
    def __init__(self, layout: CxgResourceLayout) -> None:
        super().__init__(layout, backend=self)  # type: ignore[arg-type]

    @property
    def model_name(self) -> str:  # type: ignore[override]
        return "dummy"

    def embed(
        self,
        chunks,
        *,
        metadata: dict[str, str] | None = None,
    ):  # type: ignore[override]
        return [[float(len(chunk))] for chunk in chunks]

    def similarity_search(self, article_id: str, query: str, top_k: int = 3):  # type: ignore[override]
        class Chunk:
            def __init__(self, text):
                self.text = text

        return [Chunk("Alpha chunk text"), Chunk("Another alpha snippet")]


def _bundle(layout: CxgResourceLayout) -> PreparedAnnotationBundle:
    article_id = "DOI:alpha"
    slug = normalise_identifier(article_id)
    # Ensure fallback text is longer than retrieved snippets so metrics reflect a reduction
    full_text = "Alpha full article text " * 10
    (layout.publications_dir / f"{slug}.txt").write_text(full_text, encoding="utf-8")
    record = AnnotationRecord(
        dataset_name="demo",
        annotation_text="alpha",
        article_id_doi=article_id,
    )
    return PreparedAnnotationBundle(
        annotations=[record],
        article_to_annotations={article_id: [record]},
        dataset_names=["demo"],
    )


def test_prompt_metrics_logs(tmp_path: Path):
    layout = CxgResourceLayout(resources_dir=tmp_path)
    layout.ensure_directories()
    bundle = _bundle(layout)

    log_path = tmp_path / "metrics.log"
    handler = logging.FileHandler(log_path)
    logger = logging.getLogger("amica.services.expansion_service")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    settings = CxgPipelineSettings(vector_store_enabled=True)
    agent = DummyAgent([])
    vector_store = DummyVectorStore(layout)
    service = ExpansionService(
        layout,
        settings=settings,
        agent=agent,
        vector_store=vector_store,
        retrieval_top_k=1,
    )

    asyncio.run(service.expand_annotations(bundle))

    handler.flush()
    logger.removeHandler(handler)

    metrics_lines = [
        line for line in log_path.read_text().splitlines() if "prompt_metrics" in line
    ]
    assert metrics_lines, "Expected prompt metrics log entries"
    payload = json.loads(metrics_lines[0].split("prompt_metrics", 1)[1].strip())
    assert payload["context_chars"] < payload["original_chars"]
