from __future__ import annotations

import asyncio
from collections.abc import Iterable
from pathlib import Path

import pytest

from amica.graphs import (
    CxgGraphDependencies,
    build_cxg_annotate_graph,
    run_cxg_workflow,
)
from amica.utils.cxg import (
    AnnotationRecord,
    CxgPipelineSettings,
    CxgResourceLayout,
    PreparedAnnotationBundle,
)


class DummyDatasetLoader:
    def __init__(self, bundle: PreparedAnnotationBundle) -> None:
        self._bundle = bundle

    def load(self) -> PreparedAnnotationBundle:
        return self._bundle


class DummyPublicationFetcher:
    def __init__(self) -> None:
        self.requested: list[str] = []

    def ensure_text_assets(self, dois: Iterable[str]):
        values = list(dois)
        self.requested.extend(values)
        return set(values)


class DummyExpansionService:
    async def expand_annotations(self, bundle: PreparedAnnotationBundle) -> None:
        for record in bundle.annotations:
            record.enrichment = {"name": record.annotation_text}


class DummyGroundingService:
    async def ground_annotations(self, bundle: PreparedAnnotationBundle) -> None:
        for record in bundle.annotations:
            record.grounding_cl_id = "CL:0000000"
            record.grounding_cl_label = "dummy"


@pytest.mark.unit
def test_cxg_workflow_runs_with_dummy_services(tmp_path: Path) -> None:
    annotation = AnnotationRecord(
        dataset_name="demo",
        annotation_text="cell",
        article_id_doi="DOI:foo/bar",
    )
    bundle = PreparedAnnotationBundle(
        annotations=[annotation],
        article_to_annotations={annotation.article_id_doi: [annotation]},
        dataset_names=["demo"],
    )

    layout = CxgResourceLayout(resources_dir=tmp_path)
    settings = CxgPipelineSettings(test_mode=True, test_annotations_count=1)

    publication_fetcher = DummyPublicationFetcher()
    deps = CxgGraphDependencies(
        graph=build_cxg_annotate_graph(),
        settings=settings,
        layout=layout,
        dataset_loader=DummyDatasetLoader(bundle),
        publication_fetcher=publication_fetcher,
        expansion_service=DummyExpansionService(),
        grounding_service=DummyGroundingService(),
    )

    result = asyncio.run(
        run_cxg_workflow(
            settings=settings,
            layout=layout,
            deps=deps,
        )
    )

    assert result is bundle
    assert annotation.grounding_cl_id == "CL:0000000"
    assert publication_fetcher.requested == [annotation.article_id_doi]
