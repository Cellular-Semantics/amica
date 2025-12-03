from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from amica.agents.paper_celltype.paper_celltype_agent import CellTypeEntry
from amica.services import ExpansionService
from amica.utils.cxg import (
    AnnotationRecord,
    CxgPipelineSettings,
    CxgResourceLayout,
    PreparedAnnotationBundle,
    normalise_identifier,
)


class DummyExpansionAgent:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, prompt: str) -> SimpleNamespace:
        self.calls += 1
        entry = CellTypeEntry(
            name="test_cell",
            full_name="Test Cell",
            paper_synonyms="",
            tissue_context="brain",
        )
        return SimpleNamespace(output=SimpleNamespace(cell_type_annotations=[entry]))


def _build_bundle(dataset_name: str, doi: str) -> PreparedAnnotationBundle:
    record = AnnotationRecord(
        dataset_name=dataset_name,
        annotation_text="test_cell",
        article_id_doi=doi,
    )
    return PreparedAnnotationBundle(
        annotations=[record],
        article_to_annotations={doi: [record]},
        dataset_names=[dataset_name],
    )


@pytest.mark.unit
def test_expansion_service_populates_enrichment(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    layout = CxgResourceLayout(resources_dir=resources)
    layout.ensure_directories()

    doi = "DOI:10.1000/demo"
    slug = normalise_identifier(doi)
    (layout.publications_dir / f"{slug}.txt").write_text("sample publication text")

    bundle = _build_bundle("demo", doi)
    agent = DummyExpansionAgent()
    service = ExpansionService(
        layout,
        settings=CxgPipelineSettings(annotations_batch_size=1),
        agent=agent,
    )

    asyncio.run(service.expand_annotations(bundle))

    record = bundle.annotations[0]
    assert record.enrichment is not None
    assert record.enrichment["full_name"] == "Test Cell"
    assert agent.calls == 1


@pytest.mark.unit
def test_expansion_service_uses_cached_results(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    layout = CxgResourceLayout(resources_dir=resources)
    layout.ensure_directories()

    doi = "DOI:10.1000/demo"
    slug = normalise_identifier(doi)
    (layout.publications_dir / f"{slug}.txt").write_text("sample publication text")

    bundle = _build_bundle("demo", doi)
    cache_dir = layout.expansions_dir / normalise_identifier("demo")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{slug}_batch_0.json"
    cache_file.write_text(
        json.dumps(
            [
                {
                    "name": "test_cell",
                    "full_name": "Cached Cell",
                    "paper_synonyms": "",
                    "tissue_context": "",
                }
            ]
        )
    )

    agent = DummyExpansionAgent()
    service = ExpansionService(
        layout,
        settings=CxgPipelineSettings(annotations_batch_size=1),
        agent=agent,
    )
    asyncio.run(service.expand_annotations(bundle))

    record = bundle.annotations[0]
    assert record.enrichment is not None
    assert record.enrichment["full_name"] == "Cached Cell"
    assert agent.calls == 0
