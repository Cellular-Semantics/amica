"""Dry-run support: describe the CXG pipeline without executing it."""

from __future__ import annotations

import dataclasses
import json

from amica.graphs.cxg_annotate import build_cxg_annotate_graph
from amica.utils.cxg import CxgPipelineSettings, CxgResourceLayout


def describe_pipeline(
    settings: CxgPipelineSettings,
    layout: CxgResourceLayout,
) -> str:
    """Return a human-readable dry-run description of the CXG pipeline.

    Prints all pipeline steps, agent system prompts, user prompt templates /
    recipes, output schemas, and the resolved settings and resource layout —
    without making any API calls or reading/writing data.

    Args:
        settings: Resolved pipeline settings to display.
        layout: Resolved resource layout to display.

    Returns:
        Multi-line string suitable for printing to stdout.
    """
    # Lazy imports break the pre-existing circular dependency chain:
    # paper_celltype_agent → paper_celltype_tools → amica.services.__init__
    # → expansion_service → paper_celltype_agent
    # Importing expansion_service first bootstraps amica.services fully before
    # paper_celltype_agent is touched, so subsequent imports hit sys.modules.
    from amica.services.expansion_service import PROMPT_TEMPLATE
    from amica.agents.paper_celltype.paper_celltype_agent import (
        SYSTEM_PROMPT as EXPANSION_SYSTEM_PROMPT,
        BiocurationOutput,
        CellTypeEntry,
    )
    from amica.agents.annotator.annotator_agent import (
        ANNOTATOR_SYSTEM_PROMPT_NEW,
        TextAnnotationResult,
    )

    graph = build_cxg_annotate_graph()
    lines: list[str] = []

    # ── Pipeline overview ──────────────────────────────────────────────────
    lines.append(f"=== Pipeline: {graph.name} ===")
    lines.append("")
    lines.append("Steps:")
    for node in graph.nodes:
        next_str = " → ".join(node.next_nodes) if node.next_nodes else "(terminal)"
        lines.append(f"  [{node.id}] → {next_str}")
        lines.append(f"    service    : {node.service}")
        lines.append(f"    description: {node.description}")
        lines.append("")

    # ── Settings ───────────────────────────────────────────────────────────
    lines.append("Settings:")
    for f in dataclasses.fields(settings):
        lines.append(f"  {f.name}: {getattr(settings, f.name)}")
    lines.append("")

    # ── Layout ─────────────────────────────────────────────────────────────
    lines.append("Resource Layout:")
    for f in dataclasses.fields(layout):
        lines.append(f"  {f.name}: {getattr(layout, f.name)}")
    lines.append("")

    # ── expand_full_names: paper_celltype agent ────────────────────────────
    lines.append("=== Agent: paper_celltype  [step: expand_full_names] ===")
    lines.append("")
    lines.append("System Prompt:")
    lines.append(_indent(EXPANSION_SYSTEM_PROMPT.strip()))
    lines.append("")
    lines.append("User Prompt Template  (placeholders: {cc_json}, {article_context}):")
    lines.append(_indent(PROMPT_TEMPLATE.strip()))
    lines.append("")
    lines.append("Output Schema (BiocurationOutput):")
    lines.append(_indent(json.dumps(BiocurationOutput.model_json_schema(), indent=2)))
    lines.append("")

    # ── ground_annotations: annotator agent ───────────────────────────────
    lines.append("=== Agent: annotator  [step: ground_annotations] ===")
    lines.append("")
    lines.append("System Prompt:")
    lines.append(_indent(ANNOTATOR_SYSTEM_PROMPT_NEW.strip()))
    lines.append("")
    lines.append(
        "User Prompt Recipe:"
        " JSON array of CellTypeEntry objects — direct output of expand_full_names."
    )
    lines.append(f"  Batch size: {settings.annotations_batch_size} records per call.")
    lines.append("")
    lines.append("Input Schema / User Prompt Payload (CellTypeEntry):")
    lines.append(_indent(json.dumps(CellTypeEntry.model_json_schema(), indent=2)))
    lines.append("")
    lines.append("Output Schema (TextAnnotationResult):")
    lines.append(
        _indent(json.dumps(TextAnnotationResult.model_json_schema(), indent=2))
    )
    lines.append("")

    return "\n".join(lines)


def _indent(text: str, prefix: str = "  ") -> str:
    """Indent every line of *text* with *prefix*."""
    return "\n".join(prefix + line for line in text.splitlines())
