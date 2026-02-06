from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from amica.agents.annotator.annotator_agent import TextAnnotation
from amica.services import GroundingService
from amica.utils.cxg import (
    AnnotationRecord,
    CxgPipelineSettings,
    CxgResourceLayout,
    PreparedAnnotationBundle,
)


class DummyGroundingAgent:
    def __init__(self) -> None:
        self.calls = 0
        self.last_payload: str | None = None

    async def run(self, payload: str) -> SimpleNamespace:
        self.calls += 1
        self.last_payload = payload
        annotation = TextAnnotation(
            input_name="test_cell",
            text="test_cell",
            cl_id="CL:0000000",
            cl_label="test",
        )
        return SimpleNamespace(output=SimpleNamespace(annotations=[annotation]))


def _bundle_with_enrichment(dataset: str) -> PreparedAnnotationBundle:
    record = AnnotationRecord(
        dataset_name=dataset,
        annotation_text="test_cell",
        article_id_doi="DOI:10.1000/demo",
        enrichment={"name": "test_cell", "full_name": "Test cell"},
    )
    return PreparedAnnotationBundle(
        annotations=[record],
        article_to_annotations={record.article_id_doi: [record]},
        dataset_names=[dataset],
    )


@pytest.mark.unit
def test_grounding_service_updates_annotations(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    layout = CxgResourceLayout(resources_dir=resources)
    layout.ensure_directories()

    bundle = _bundle_with_enrichment("demo")
    agent = DummyGroundingAgent()
    service = GroundingService(
        layout,
        settings=CxgPipelineSettings(annotations_batch_size=1),
        agent=agent,
    )

    asyncio.run(service.ground_annotations(bundle))

    record = bundle.annotations[0]
    assert record.grounding_cl_id == "CL:0000000"
    output_file = layout.output_dir / "demo" / "cell_type_annotations_un_filtered.tsv"
    assert output_file.exists()
    assert agent.calls == 1


@pytest.mark.unit
def test_grounding_service_reuses_cache(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    layout = CxgResourceLayout(resources_dir=resources)
    layout.ensure_directories()

    bundle = _bundle_with_enrichment("demo")
    cache_dir = layout.cache_dir / "demo"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "batch_0.json"
    cache_file.write_text(
        json.dumps(
            [
                {
                    "input_name": "test_cell",
                    "text": "test_cell",
                    "cl_id": "CL:0001111",
                    "cl_label": "cached",
                }
            ]
        )
    )

    agent = DummyGroundingAgent()
    service = GroundingService(
        layout,
        settings=CxgPipelineSettings(annotations_batch_size=1),
        agent=agent,
    )
    asyncio.run(service.ground_annotations(bundle))

    record = bundle.annotations[0]
    assert record.grounding_cl_id == "CL:0001111"
    assert agent.calls == 0
