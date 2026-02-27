"""Unit tests for the --dry-run pipeline description feature."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from amica.dry_run import describe_pipeline
from amica.utils.cxg import CxgPipelineSettings, CxgResourceLayout


# ── describe_pipeline content tests ──────────────────────────────────────────


@pytest.mark.unit
def test_describe_pipeline_contains_all_node_ids(tmp_path: Path) -> None:
    output = describe_pipeline(
        CxgPipelineSettings(), CxgResourceLayout(resources_dir=tmp_path)
    )
    assert "prepare_data" in output
    assert "expand_full_names" in output
    assert "ground_annotations" in output


@pytest.mark.unit
def test_describe_pipeline_contains_service_names(tmp_path: Path) -> None:
    output = describe_pipeline(
        CxgPipelineSettings(), CxgResourceLayout(resources_dir=tmp_path)
    )
    assert "cxg.prepare_data" in output
    assert "cxg.expand_full_names" in output
    assert "cxg.ground_annotations" in output


@pytest.mark.unit
def test_describe_pipeline_contains_expansion_system_prompt(tmp_path: Path) -> None:
    output = describe_pipeline(
        CxgPipelineSettings(), CxgResourceLayout(resources_dir=tmp_path)
    )
    assert "Biocuration Assistant" in output


@pytest.mark.unit
def test_describe_pipeline_contains_expansion_prompt_template_placeholders(
    tmp_path: Path,
) -> None:
    output = describe_pipeline(
        CxgPipelineSettings(), CxgResourceLayout(resources_dir=tmp_path)
    )
    assert "{cc_json}" in output
    assert "{article_context}" in output


@pytest.mark.unit
def test_describe_pipeline_contains_grounding_system_prompt(tmp_path: Path) -> None:
    output = describe_pipeline(
        CxgPipelineSettings(), CxgResourceLayout(resources_dir=tmp_path)
    )
    assert "cell ontology" in output.lower()


@pytest.mark.unit
def test_describe_pipeline_contains_output_schemas(tmp_path: Path) -> None:
    output = describe_pipeline(
        CxgPipelineSettings(), CxgResourceLayout(resources_dir=tmp_path)
    )
    assert "BiocurationOutput" in output
    assert "TextAnnotationResult" in output
    assert "CellTypeEntry" in output


@pytest.mark.unit
def test_describe_pipeline_contains_settings_fields(tmp_path: Path) -> None:
    settings = CxgPipelineSettings(annotations_batch_size=7)
    output = describe_pipeline(settings, CxgResourceLayout(resources_dir=tmp_path))
    assert "annotations_batch_size" in output
    assert "7" in output


@pytest.mark.unit
def test_describe_pipeline_contains_layout_paths(tmp_path: Path) -> None:
    output = describe_pipeline(
        CxgPipelineSettings(), CxgResourceLayout(resources_dir=tmp_path)
    )
    assert str(tmp_path) in output


@pytest.mark.unit
def test_describe_pipeline_grounding_recipe_references_batch_size(
    tmp_path: Path,
) -> None:
    settings = CxgPipelineSettings(annotations_batch_size=3)
    output = describe_pipeline(settings, CxgResourceLayout(resources_dir=tmp_path))
    # Recipe should mention that CellTypeEntry is the payload and state the batch size
    assert "CellTypeEntry" in output
    assert "3" in output


# ── CLI arg-parsing tests ─────────────────────────────────────────────────────


@pytest.mark.unit
def test_parse_args_dry_run_flag() -> None:
    import cxg_annotate  # available via conftest sys.path

    args = cxg_annotate.parse_args(["--dry-run"])
    assert args.dry_run is True


@pytest.mark.unit
def test_parse_args_dry_run_default_false() -> None:
    import cxg_annotate

    args = cxg_annotate.parse_args([])
    assert args.dry_run is False


# ── _async_main wiring test ───────────────────────────────────────────────────


@pytest.mark.unit
def test_async_main_dry_run_skips_workflow(tmp_path: Path, monkeypatch) -> None:
    import cxg_annotate

    workflow_called: list[bool] = []

    async def fake_workflow(**kwargs):  # type: ignore[misc]
        workflow_called.append(True)

    monkeypatch.setattr(cxg_annotate, "run_cxg_workflow", fake_workflow)
    monkeypatch.setattr(cxg_annotate, "bootstrap", lambda: None)
    monkeypatch.setenv("CXG_RESOURCES_DIR", str(tmp_path))

    args = cxg_annotate.parse_args(["--dry-run"])
    asyncio.run(cxg_annotate._async_main(args))

    assert not workflow_called


@pytest.mark.unit
def test_async_main_dry_run_prints_output(tmp_path: Path, monkeypatch, capsys) -> None:
    import cxg_annotate

    async def fake_workflow(**kwargs):  # type: ignore[misc]
        pass

    monkeypatch.setattr(cxg_annotate, "run_cxg_workflow", fake_workflow)
    monkeypatch.setattr(cxg_annotate, "bootstrap", lambda: None)
    monkeypatch.setenv("CXG_RESOURCES_DIR", str(tmp_path))

    args = cxg_annotate.parse_args(["--dry-run"])
    asyncio.run(cxg_annotate._async_main(args))

    captured = capsys.readouterr()
    assert "prepare_data" in captured.out
    assert "expand_full_names" in captured.out
    assert "ground_annotations" in captured.out
