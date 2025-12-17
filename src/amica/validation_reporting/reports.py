"""Markdown rendering helpers for validation reporting."""

from __future__ import annotations

from textwrap import dedent

from .stats import FilteredStats, ImprovedExample, RawStats


def build_filtered_markdown(stats: FilteredStats) -> str:
    """Create the filtered granularity markdown report."""
    lines: list[str] = ["# Annotation Granularity Report (Filtered)"]
    lines.append(
        "> **Note:** This report excludes 'Broad term' and 'Overlaps' matches to reduce false regressions.\n"
    )

    if not stats.ontology_available:
        lines.append(
            "> Warning: Ontology lookups were unavailable, so improved/regression counts may be understated.\n"
        )

    lines.append("## Aggregate Statistics")
    lines.append(f"**Total Annotations Analyzed:** {stats.total_filtered}")
    lines.append(f"**Excluded (Noisy Data):** {stats.excluded_broad}\n")

    lines.append("| Category | Count | Percentage | Description |")
    lines.append("| :--- | :--- | :--- | :--- |")

    descriptions = {
        "improved_granularity": "Agent provided a more specific or context-aware term.",
        "exact_match": "Agent matched the author's term exactly.",
        "regression": "Agent provided a less specific term (ancestor).",
        "no_match_found": "Agent could not find a CL term (potential new term).",
        "other": "Agent term is unrelated to the author term.",
    }

    categories = [
        ("improved_granularity", stats.improved_granularity),
        ("exact_match", stats.exact_match),
        ("regression", stats.regression),
        ("no_match_found", stats.no_match_found),
        ("other", stats.other),
    ]

    total = max(stats.total_filtered, 1)
    for key, count in categories:
        percent = (count / total) * 100
        lines.append(
            f"| {key.replace('_', ' ').title()} | {count} | {percent:.2f}% | {descriptions[key]} |"
        )

    return "\n".join(lines) + "\n"


def build_examples_markdown(examples: list[ImprovedExample]) -> str:
    """Create the markdown report highlighting improved granularity examples."""
    lines = ["# Good Examples of Improved Granularity"]
    if not examples:
        lines.append(
            "\n_No improved examples were detected (ontology lookups may have been unavailable)._"
        )
        return "\n".join(lines) + "\n"

    current_dataset: str | None = None
    for example in examples:
        if example.dataset != current_dataset:
            lines.append(f"\n## Dataset: {example.dataset}")
            current_dataset = example.dataset
        lines.append(f"- **Annotation Text:** {example.annotation_text}")
        lines.append(f"- **Author's Mapping:** {example.author_mapping}")
        lines.append(f"- **Agent's Mapping:** {example.agent_mapping}")
        if example.enrichment:
            lines.append(f"- **Enrichment Info:** `{example.enrichment}`")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_raw_stats_markdown(stats: RawStats) -> str:
    """Render the raw aggregate statistics similar to the legacy script output."""
    if stats.total_annotations == 0:
        return "# Raw Grounding Statistics\n\n_No annotations were found to analyze._\n"

    warning = ""
    if not stats.ontology_available:
        warning = "> Warning: Ontology lookups were unavailable; improved/regression counts may be understated.\n\n"

    lines = [
        "# Raw Grounding Statistics",
        warning,
        f"Total Annotations Analyzed: **{stats.total_annotations}**",
        "",
        "| Category | Count | Percentage |",
        "| :--- | :--- | :--- |",
    ]
    total = max(stats.total_annotations, 1)
    rows = [
        ("Improved Granularity", stats.improved),
        ("Identical Mapping", stats.identical),
        ("Less Specific Mapping", stats.less_specific),
        ("No Match Found", stats.no_match),
        ("Other / Different Branch", stats.other),
    ]
    for label, count in rows:
        lines.append(f"| {label} | {count} | {(count / total) * 100:.2f}% |")
    return "\n".join(filter(None, lines)) + "\n"
