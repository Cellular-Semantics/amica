from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from amica.services import DatasetLoader, PublicationFetcher
from amica.utils.cxg import CxgPipelineSettings, CxgResourceLayout


def _write_sample_tsv(path: Path, rows: list[dict[str, str]]) -> None:
    df = pd.DataFrame(rows)
    df.to_csv(path, sep="\t", index=False)


@pytest.mark.unit
def test_dataset_loader_parses_annotations(tmp_path: Path) -> None:
    """DatasetLoader should ingest TSV rows into AnnotationRecord objects."""
    resources = tmp_path / "resources"
    layout = CxgResourceLayout(resources_dir=resources)
    layout.ensure_directories()
    _write_sample_tsv(
        layout.input_dir / "demo.tsv",
        [
            {
                "author_cell_type": "Goblet cell",
                "CL_ID": "CL:0000160",
                "CL_label": "goblet cell",
                "reference": "https://doi.org/10.1000/demo",
            }
        ],
    )
    loader = DatasetLoader(layout)
    bundle = loader.load()

    assert len(bundle.annotations) == 1
    record = bundle.annotations[0]
    assert record.annotation_text == "Goblet cell"
    assert record.cl_id == "CL:0000160"
    assert record.article_id_doi == "DOI:10.1000/demo"
    assert bundle.dataset_names == ["demo"]


@pytest.mark.unit
def test_dataset_loader_respects_test_mode(tmp_path: Path) -> None:
    """Test mode should truncate annotations per the configured limit."""
    resources = tmp_path / "resources"
    layout = CxgResourceLayout(resources_dir=resources)
    layout.ensure_directories()
    rows = [
        {
            "author_cell_type": f"cell_{idx}",
            "CL_ID": f"CL:{idx:07d}",
            "CL_label": f"label_{idx}",
            "reference": "https://doi.org/10.1000/demo",
        }
        for idx in range(5)
    ]
    _write_sample_tsv(layout.input_dir / "demo.tsv", rows)
    settings = CxgPipelineSettings(test_mode=True, test_annotations_count=2)
    loader = DatasetLoader(layout, settings=settings)
    bundle = loader.load()

    assert len(bundle.annotations) == 2
    assert len(bundle.article_to_annotations) == 1


@pytest.mark.unit
def test_publication_fetcher_downloads_missing_files(monkeypatch, tmp_path: Path) -> None:
    """PublicationFetcher should write text files when not cached."""
    captured = {}

    def fake_get_doi_text(doi: str) -> str:
        captured["last"] = doi
        return "full text"

    monkeypatch.setattr(
        "amica.services.publication_fetcher.get_doi_text",
        fake_get_doi_text,
    )

    resources = tmp_path / "resources"
    layout = CxgResourceLayout(resources_dir=resources)
    layout.ensure_directories()
    fetcher = PublicationFetcher(layout)

    dois = {"DOI:10.1000/demo"}
    downloaded = fetcher.ensure_text_assets(dois)

    assert downloaded == dois
    assert captured["last"] == "DOI:10.1000/demo"
    stored_file = layout.publications_dir / "DOI_10_1000_demo.txt"
    assert stored_file.exists()
    assert stored_file.read_text() == "full text"
