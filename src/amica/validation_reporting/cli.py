"""Public entrypoints for validation-report generation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from oaklib import get_adapter

from amica.utils.cxg import CxgResourceLayout

from .config import ValidationPaths
from .data_loader import MatchTypeResolver, load_grounding_datasets
from .reports import (
    build_examples_markdown,
    build_filtered_markdown,
    build_raw_stats_markdown,
)
from .stats import (
    collect_improved_examples,
    compute_filtered_stats,
    compute_raw_stats,
    reset_ontology_tracker,
)

LOGGER = logging.getLogger(__name__)


def _initialise_adapter(skip_ontology: bool, adapter_spec: str | None) -> Any | None:
    if skip_ontology:
        LOGGER.warning("Ontology lookups skipped per CLI flag.")
        return None
    spec = adapter_spec or "ols:cl"
    try:
        LOGGER.info("Initializing ontology adapter (%s) ...", spec)
        adapter = get_adapter(spec)
        LOGGER.info("Ontology adapter ready.")
        return adapter
    except Exception as exc:  # pragma: no cover - network failures
        LOGGER.warning("Could not initialize ontology adapter %s: %s", spec, exc)
        return None


def generate_reports(
    *,
    include_filtered: bool = True,
    include_examples: bool = True,
    include_raw_stats: bool = True,
    output_root: Path | None = None,
    raw_output_dir: Path | None = None,
    match_type_dir: Path | None = None,
    reports_dir: Path | None = None,
    skip_ontology: bool = False,
    adapter_spec: str | None = None,
) -> dict[str, Path]:
    """Generate requested validation reports using existing CXG outputs."""
    layout = CxgResourceLayout.from_env()
    paths = ValidationPaths.from_layout(
        layout,
        output_root=output_root,
        raw_output_dir=raw_output_dir,
        match_type_dir=match_type_dir,
        reports_dir=reports_dir,
    )

    datasets = load_grounding_datasets(paths.raw_output)
    resolver = MatchTypeResolver(paths.match_type_inputs)
    adapter = _initialise_adapter(skip_ontology=skip_ontology, adapter_spec=adapter_spec)

    paths.ensure_report_dir()
    written: dict[str, Path] = {}

    if include_filtered:
        reset_ontology_tracker()
        filtered_stats = compute_filtered_stats(datasets, resolver, adapter)
        filtered_content = build_filtered_markdown(filtered_stats)
        filtered_path = paths.reports_dir / "filtered_granularity_report.md"
        filtered_path.write_text(filtered_content)
        written["filtered"] = filtered_path
        LOGGER.info("Filtered granularity report written to %s", filtered_path)

    if include_examples:
        reset_ontology_tracker()
        examples = collect_improved_examples(datasets, adapter)
        examples_content = build_examples_markdown(examples)
        examples_path = paths.reports_dir / "granularity_report.md"
        examples_path.write_text(examples_content)
        written["examples"] = examples_path
        LOGGER.info("Improved examples report written to %s", examples_path)

    if include_raw_stats:
        reset_ontology_tracker()
        raw_stats = compute_raw_stats(datasets, adapter)
        raw_content = build_raw_stats_markdown(raw_stats)
        raw_path = paths.reports_dir / "raw_stats_report.md"
        raw_path.write_text(raw_content)
        written["raw_stats"] = raw_path
        LOGGER.info("Raw stats report written to %s", raw_path)

    return written
