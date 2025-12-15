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


class DummyVectorStore:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str]] = []

    def ensure_index(self, article_id: str, article_text: str) -> None:
        self.requests.append((article_id, article_text))

    def similarity_search(self, article_id: str, query: str, top_k: int = 2):
        return []


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


@pytest.mark.unit
def test_cxg_dependencies_use_vector_store(tmp_path: Path) -> None:
    settings = CxgPipelineSettings(vector_store_enabled=True)
    layout = CxgResourceLayout(resources_dir=tmp_path)
    dummy_vector_store = DummyVectorStore()

    deps = CxgGraphDependencies(
        graph=build_cxg_annotate_graph(),
        settings=settings,
        layout=layout,
        vector_store=dummy_vector_store,
    )

    assert deps.expansion_service is not None
    assert deps.expansion_service.vector_store is dummy_vector_store


@pytest.mark.unit
def test_vector_store_failure_disables_feature(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    class ExplodingBackend:
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("boom")

    monkeypatch.setattr(
        "amica.graphs.cxg_annotate.OpenAIEmbeddingBackend", ExplodingBackend
    )

    settings = CxgPipelineSettings(vector_store_enabled=True)
    layout = CxgResourceLayout(resources_dir=tmp_path)

    with caplog.at_level("WARNING"):
        deps = CxgGraphDependencies(
            graph=build_cxg_annotate_graph(),
            settings=settings,
            layout=layout,
        )

    assert deps.expansion_service is not None
    assert deps.expansion_service.vector_store is None
    assert deps.settings.vector_store_enabled is False
    assert any("Vector store disabled" in message for message in caplog.messages)
