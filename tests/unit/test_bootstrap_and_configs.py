from __future__ import annotations

from pathlib import Path

import pytest

from amica import bootstrap
from amica.agents.annotator.annotator_config import get_config as get_annotator_config
from amica.agents.paper_celltype.paper_celltype_config import get_config as get_paper_ct_config
from amica.utils.cxg import (
    CxgPipelineSettings,
    CxgResourceLayout,
    load_cxg_configuration,
)
from amica.utils.workdir import WorkDir


@pytest.mark.unit
def test_bootstrap_loads_dotenv(tmp_path: Path, monkeypatch) -> None:
    """Ensure bootstrap loads environment variables from explicit path."""
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text("TEST_KEY=123\n")

    loaded = {}

    def fake_load_dotenv(path=None):
        loaded["path"] = path

    monkeypatch.setattr("amica.load_dotenv", fake_load_dotenv)
    bootstrap(dotenv_path=str(dotenv_file))
    assert loaded["path"] == str(dotenv_file)


@pytest.mark.unit
def test_annotator_config_uses_custom_workdir(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "annotator"
    monkeypatch.setenv("AURELIAN_WORKDIR", str(path))
    config = get_annotator_config()
    assert isinstance(config.workdir, WorkDir)
    assert Path(config.workdir.location) == path


@pytest.mark.unit
def test_paper_ct_config_default_workdir(monkeypatch) -> None:
    """Ensure PaperCTDependencies creates a workdir when unspecified."""
    monkeypatch.delenv("AURELIAN_WORKDIR", raising=False)
    config = get_paper_ct_config()
    assert isinstance(config.workdir, WorkDir)


@pytest.mark.unit
def test_cxg_settings_from_env(monkeypatch) -> None:
    monkeypatch.setenv("CXG_ANNOTATIONS_BATCH_SIZE", "7")
    monkeypatch.setenv("CXG_TEST_MODE", "true")
    monkeypatch.setenv("CXG_TEST_ANNOTATIONS_COUNT", "3")
    settings = CxgPipelineSettings.from_env()
    assert settings.annotations_batch_size == 7
    assert settings.test_mode is True
    assert settings.test_annotations_count == 3


@pytest.mark.unit
def test_cxg_resource_layout_from_env(monkeypatch, tmp_path: Path) -> None:
    custom = tmp_path / "cxg"
    monkeypatch.setenv("CXG_RESOURCES_DIR", str(custom))
    layout = CxgResourceLayout.from_env()
    assert layout.resources_dir == custom.resolve()
    layout.ensure_directories()
    assert layout.input_dir.exists()


@pytest.mark.unit
def test_load_cxg_configuration_returns_pair(monkeypatch) -> None:
    monkeypatch.setenv("CXG_RESOURCES_DIR", "/tmp/cxg")
    settings, layout = load_cxg_configuration()
    assert isinstance(settings, CxgPipelineSettings)
    assert isinstance(layout, CxgResourceLayout)
