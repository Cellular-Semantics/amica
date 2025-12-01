"""Lightweight workdir helpers used by agent configuration objects."""

from __future__ import annotations

import tempfile
from abc import ABC
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class WorkDir:
    """Filesystem-backed working directory manager.

    Example:
        .. code-block:: python

            wd = WorkDir()
            wd.write_file("example.txt", "hello")
            assert wd.check_file_exists("example.txt")
            assert wd.read_file("example.txt") == "hello"
    """

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
        """Return an absolute file path inside the working directory.

        Args:
            file_name: Relative file name to resolve within the workdir.

        Returns:
            Absolute :class:`Path` pointing to the requested file.
        """
        self._ensure_location()
        return Path(self.location) / file_name

    def read_file(self, file_name: str) -> str:
        """Read text content from a file stored in the working directory.

        Args:
            file_name: Relpath of the file to read.

        Returns:
            Full text contents of the file.
        """
        file_path = self.get_file_path(file_name)
        return file_path.read_text()

    def check_file_exists(self, file_name: str) -> bool:
        """Return True if the given file exists within the working directory.

        Args:
            file_name: Relative file name to check.

        Returns:
            ``True`` when the resolved file exists, ``False`` otherwise.
        """
        return self.get_file_path(file_name).exists()

    def write_file(self, file_name: str, content: str) -> None:
        """Write text content into a file contained in the working directory.

        Args:
            file_name: Relative path to the file to create/overwrite.
            content: Full text payload to write.
        """
        file_path = self.get_file_path(file_name)
        file_path.write_text(content)

    def delete_file(self, file_name: str) -> None:
        """Delete a file from the working directory if present.

        Args:
            file_name: Relative path to remove.
        """
        file_path = self.get_file_path(file_name)
        if file_path.exists():
            file_path.unlink()

    def list_file_names(self) -> List[str]:
        """List non-recursive file names contained in the working directory.

        Returns:
            Flat list of filenames (no directories) located directly under
            :attr:`location`.
        """
        self._ensure_location()
        return [
            entry.name
            for entry in Path(self.location).iterdir()
            if entry.is_file()
        ]


@dataclass
class HasWorkdir(ABC):
    """Mixin to provide a :class:`WorkDir` attribute to dependency objects."""

    workdir: Optional[WorkDir] = field(default=None)

    def ensure_workdir(self) -> WorkDir:
        """Return an initialised work directory, creating one if required.

        Returns:
            A valid :class:`WorkDir` instance ready for use.
        """
        if self.workdir is None:
            self.workdir = WorkDir()
        return self.workdir


__all__ = ["WorkDir", "HasWorkdir"]
