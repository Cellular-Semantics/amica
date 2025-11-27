"""Lightweight workdir helpers used by agent configuration objects."""

from __future__ import annotations

import tempfile
from abc import ABC
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class WorkDir:
    """Simple filesystem-backed working directory manager."""

    location: str = field(default_factory=lambda: tempfile.mkdtemp())

    @classmethod
    def create_temporary_workdir(cls) -> "WorkDir":
        """Create a new temporary working directory."""
        temp_dir = tempfile.mkdtemp()
        return cls(location=temp_dir)

    def _ensure_location(self) -> None:
        Path(self.location).mkdir(parents=True, exist_ok=True)

    def __post_init__(self) -> None:
        self._ensure_location()

    def get_file_path(self, file_name: str) -> Path:
        """Return an absolute Path inside the workdir."""
        self._ensure_location()
        return Path(self.location) / file_name

    def read_file(self, file_name: str) -> str:
        """Read a file inside the workdir."""
        file_path = self.get_file_path(file_name)
        return file_path.read_text()

    def check_file_exists(self, file_name: str) -> bool:
        """Return True if file exists within the workdir."""
        return self.get_file_path(file_name).exists()

    def write_file(self, file_name: str, content: str) -> None:
        """Write text content into a file within the workdir."""
        file_path = self.get_file_path(file_name)
        file_path.write_text(content)

    def delete_file(self, file_name: str) -> None:
        """Remove a file from the workdir if it exists."""
        file_path = self.get_file_path(file_name)
        if file_path.exists():
            file_path.unlink()

    def list_file_names(self) -> List[str]:
        """List non-recursive file names contained in the workdir."""
        self._ensure_location()
        return [
            entry.name
            for entry in Path(self.location).iterdir()
            if entry.is_file()
        ]


@dataclass
class HasWorkdir(ABC):
    """Mixin to provide a WorkDir attribute to agent dependencies."""

    workdir: Optional[WorkDir] = field(default=None)

    def ensure_workdir(self) -> WorkDir:
        """Return an initialised WorkDir, creating one if needed."""
        if self.workdir is None:
            self.workdir = WorkDir()
        return self.workdir


__all__ = ["WorkDir", "HasWorkdir"]
