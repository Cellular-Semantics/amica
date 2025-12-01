from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from amica.graphs import run_cxg_workflow
from amica.utils.cxg import (
    CxgPipelineSettings,
    CxgResourceLayout,
    normalise_identifier,
)

REQUIRED_ENV_VARS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")


SUBSET_DATASET = Path("tests/data/cxg_subset.tsv")


@pytest.mark.integration
def test_cxg_pipeline_smoke(tmp_path: Path) -> None:
    """Run the CXG workflow end-to-end against a real dataset subset."""
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    assert not missing, f"Missing integration environment variables: {missing}"
    assert SUBSET_DATASET.exists(), f"Subset dataset missing: {SUBSET_DATASET}"

    resources = tmp_path / "resources"
    layout = CxgResourceLayout(resources_dir=resources)
    layout.ensure_directories()

    subset_path = layout.input_dir / SUBSET_DATASET.name
    subset_path.write_text(SUBSET_DATASET.read_text())

    settings = CxgPipelineSettings(
        annotations_batch_size=1,
        test_mode=False,
        test_annotations_count=0,
    )

    result = asyncio.run(run_cxg_workflow(settings=settings, layout=layout))
    subset_name = SUBSET_DATASET.stem
    assert result.dataset_names == [subset_name]
    output_file = (
        layout.output_dir / subset_name / "cell_type_annotations_un_filtered.tsv"
    )
    assert output_file.exists()
