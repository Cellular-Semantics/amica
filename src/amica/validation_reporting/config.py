"""Shared configuration helpers for validation report generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from amica.utils.cxg import CxgResourceLayout


def _resolve(path: Path | None) -> Path | None:
    if path is None:
        return None
    return Path(path).expanduser().resolve()


@dataclass(slots=True)
class ValidationPaths:
    """Filesystem locations that contain CXG outputs + validation reports."""

    raw_output: Path
    match_type_inputs: Path
    reports_dir: Path

    @classmethod
    def from_layout(
        cls,
        layout: CxgResourceLayout,
        *,
        output_root: Path | None = None,
        raw_output_dir: Path | None = None,
        match_type_dir: Path | None = None,
        reports_dir: Path | None = None,
    ) -> "ValidationPaths":
        """Build directory references from the CXG resource layout."""

        base_output: Path = _resolve(output_root) or layout.output_dir
        return cls(
            raw_output=_resolve(raw_output_dir) or base_output,
            match_type_inputs=_resolve(match_type_dir) or layout.match_type_dir,
            reports_dir=_resolve(reports_dir) or (base_output / "reports"),
        )

    def ensure_report_dir(self) -> None:
        """Create the reports directory if it does not exist."""
        self.reports_dir.mkdir(parents=True, exist_ok=True)
