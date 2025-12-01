from __future__ import annotations

from pathlib import Path

import pytest

from amica.utils.workdir import HasWorkdir, WorkDir


@pytest.mark.unit
def test_workdir_basic_file_lifecycle(tmp_path: Path) -> None:
    """Ensure the WorkDir helper reads/writes files correctly."""
    wd = WorkDir(location=str(tmp_path / "wd"))
    wd.write_file("example.txt", "hello world")
    assert wd.check_file_exists("example.txt")
    assert wd.read_file("example.txt") == "hello world"

    files = wd.list_file_names()
    assert files == ["example.txt"]

    wd.delete_file("example.txt")
    assert not wd.check_file_exists("example.txt")


@pytest.mark.unit
def test_has_workdir_provides_default_workdir(tmp_path: Path) -> None:
    """HasWorkdir.ensure_workdir() should create a working directory when absent."""

    class MyDeps(HasWorkdir):
        pass

    deps = MyDeps()
    created = deps.ensure_workdir()
    assert isinstance(created, WorkDir)
    assert created.check_file_exists("placeholder.txt") is False
