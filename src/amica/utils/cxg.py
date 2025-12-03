"""Shared CXG configuration, models, and helper utilities."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from amica.agents.paper_celltype.paper_celltype_agent import CellTypeEntry


def _default_resources_dir() -> Path:
    env_override = os.environ.get("CXG_RESOURCES_DIR")
    if env_override:
        return Path(env_override).expanduser()
    return Path("resources") / "cxg"


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class CxgPipelineSettings:
    """Runtime switches that control how the CXG workflow runs."""

    annotations_batch_size: int = 5
    test_mode: bool = False
    test_annotations_count: int = 4

    @classmethod
    def from_env(cls) -> CxgPipelineSettings:
        """Build settings from environment variables."""
        return cls(
            annotations_batch_size=_env_int("CXG_ANNOTATIONS_BATCH_SIZE", 5),
            test_mode=_env_bool("CXG_TEST_MODE", False),
            test_annotations_count=_env_int("CXG_TEST_ANNOTATIONS_COUNT", 4),
        )


@dataclass(slots=True)
class CxgResourceLayout:
    """Describe on-disk folders the CXG pipeline reads from or writes to."""

    resources_dir: Path = field(default_factory=_default_resources_dir)
    cache_dir: Path = field(init=False)
    expansions_dir: Path = field(init=False)
    publications_dir: Path = field(init=False)
    input_dir: Path = field(init=False)
    output_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        base = Path(self.resources_dir).expanduser().resolve()
        self.resources_dir = base
        self.cache_dir = base / "cache"
        self.expansions_dir = base / "expansions"
        self.publications_dir = base / "publications"
        self.input_dir = base / "input"
        self.output_dir = base / "output"

    @classmethod
    def from_env(cls) -> CxgResourceLayout:
        """Construct a layout using environment variables."""
        override = os.environ.get("CXG_RESOURCES_DIR")
        if override:
            return cls(resources_dir=Path(override).expanduser())
        return cls()

    def ensure_directories(self) -> None:
        """Create the directory structure if it does not already exist."""
        for path in (
            self.input_dir,
            self.cache_dir,
            self.expansions_dir,
            self.publications_dir,
            self.output_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@dataclass(slots=True)
class AnnotationRecord:
    """Structured representation of a single CXG annotation row."""

    dataset_name: str
    annotation_text: str
    article_id_doi: str
    cl_id: str | None = None
    cl_label: str | None = None
    enrichment: CellTypeEntry | dict[str, Any] | None = None
    grounding_cl_id: str | None = None
    grounding_cl_label: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a serialisable form for pandas/DataFrame consumers."""
        payload: dict[str, Any] = {
            "dataset_name": self.dataset_name,
            "annotation_text": self.annotation_text,
            "article_id_doi": self.article_id_doi,
            "cl_id": self.cl_id,
            "cl_label": self.cl_label,
            "grounding_cl_id": self.grounding_cl_id,
            "grounding_cl_label": self.grounding_cl_label,
        }
        if self.enrichment:
            if isinstance(self.enrichment, CellTypeEntry):
                payload["enrichment"] = self.enrichment.model_dump()
            else:
                payload["enrichment"] = self.enrichment
        return payload


@dataclass(slots=True)
class PreparedAnnotationBundle:
    """Outputs from the dataset loading/preparation stage."""

    annotations: list[AnnotationRecord] = field(default_factory=list)
    article_to_annotations: dict[str, list[AnnotationRecord]] = field(
        default_factory=dict
    )
    dataset_names: list[str] = field(default_factory=list)


def normalise_identifier(value: str) -> str:
    """Convert arbitrary identifiers into filesystem-safe fragments."""
    return value.replace("/", "_").replace(":", "_").replace(".", "_")


def load_cxg_configuration() -> tuple[CxgPipelineSettings, CxgResourceLayout]:
    """Return CXG runtime settings and resource layout derived from env vars.

    Returns:
        Tuple of (:class:`CxgPipelineSettings`, :class:`CxgResourceLayout`).
    """
    return CxgPipelineSettings.from_env(), CxgResourceLayout.from_env()


__all__ = [
    "CxgPipelineSettings",
    "CxgResourceLayout",
    "AnnotationRecord",
    "PreparedAnnotationBundle",
    "normalise_identifier",
    "load_cxg_configuration",
]
