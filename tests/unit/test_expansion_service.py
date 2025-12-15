from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
from amica.services import ExpansionService
from amica.services.vector_store import DocumentVectorStore
from amica.utils.cxg import (
    AnnotationRecord,
    CxgPipelineSettings,
    CxgResourceLayout,
    PreparedAnnotationBundle,
    normalise_identifier,
)

pytestmark = pytest.mark.unit


@dataclass
class FakeCellEntry:
    name: str
    full_name: str
    paper_synonyms: str
    tissue_context: str

    def model_dump(self) -> dict:
        return {
            "name": self.name,
            "full_name": self.full_name,
            "paper_synonyms": self.paper_synonyms,
            "tissue_context": self.tissue_context,
        }


class DummyExpansionAgent:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, prompt: str) -> SimpleNamespace:
        self.calls += 1
        entry = FakeCellEntry(
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


@dataclass
class RecordingAgent:
    prompts: list[str]

    def __init__(self) -> None:
        self.prompts = []

    async def run(self, prompt: str):  # type: ignore[override]
        self.prompts.append(prompt)

        class _Result:
            def __init__(self) -> None:
                self.output = SimpleNamespace(cell_type_annotations=[])

        return _Result()


@dataclass
class KeywordEmbeddingBackend:
    model_name: str = "keyword"

    def embed(
        self,
        chunks: list[str],
        *,
        metadata: dict[str, str] | None = None,
    ) -> list[list[float]]:  # type: ignore[override]
        vectors: list[list[float]] = []
        for chunk in chunks:
            token = chunk.lower()
            if "alpha" in token:
                vectors.append([1.0, 0.0])
            elif "beta" in token:
                vectors.append([0.0, 1.0])
            else:
                vectors.append([1.0, 1.0])
        return vectors


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio("asyncio")
async def test_expansion_uses_retrieved_context(tmp_path: Path):
    layout = CxgResourceLayout(resources_dir=tmp_path / "cxg")
    layout.ensure_directories()

    dataset = "ds1"
    doi = "DOI:ALPHA"
    slug = normalise_identifier(doi)
    article_text = "Alpha neurons regulate signals. Beta glia provide support."
    publication_path = layout.publications_dir / f"{slug}.txt"
    publication_path.write_text(article_text, encoding="utf-8")

    record = AnnotationRecord(
        dataset_name=dataset,
        annotation_text="Alpha cells",
        article_id_doi=doi,
    )
    bundle = PreparedAnnotationBundle(
        annotations=[record],
        article_to_annotations={doi: [record]},
        dataset_names=[dataset],
    )

    backend = KeywordEmbeddingBackend()
    vector_store = DocumentVectorStore(
        layout,
        backend=backend,
        chunk_chars=30,
        chunk_overlap=5,
    )
    agent = RecordingAgent()
    settings = CxgPipelineSettings(annotations_batch_size=5)
    service = ExpansionService(
        layout,
        settings=settings,
        agent=agent,
        vector_store=vector_store,
        retrieval_top_k=1,
    )

    await service.expand_annotations(bundle)

    assert agent.prompts, "Expansion service should have invoked the agent"
    prompt = agent.prompts[0]
    assert "Alpha neurons regulate signals" in prompt
    assert "Beta glia provide support" not in prompt
