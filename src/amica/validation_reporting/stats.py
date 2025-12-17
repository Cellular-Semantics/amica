"""Pure aggregation helpers for validation reporting."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from .data_loader import MatchTypeResolver

LOGGER = logging.getLogger(__name__)
_ONTOLOGY_FAILURE = False

def _clean_str(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _normalise_curie(entry: Any) -> str:
    """Best-effort extraction of a CL-style identifier from oaklib responses."""
    if isinstance(entry, str):
        return entry.strip()
    if isinstance(entry, Iterable):
        for part in entry:
            if isinstance(part, str) and part.startswith("CL:"):
                return part.strip()
    return _clean_str(entry)


def _get_ancestors(
    adapter: Any | None, cl_id: str, predicates: Sequence[str]
) -> set[str]:
    global _ONTOLOGY_FAILURE
    if adapter is None or not cl_id:
        return set()
    # Validate that cl_id is a proper CL identifier before attempting lookup
    if not cl_id.startswith("CL:"):
        return set()
    try:
        values = adapter.ancestors(cl_id, predicates=list(predicates))
    except Exception as exc:
        if not _ONTOLOGY_FAILURE:
            LOGGER.warning(
                "Ontology ancestor lookup failed for %s (predicates=%s): %s",
                cl_id,
                predicates,
                exc,
            )
        _ONTOLOGY_FAILURE = True
        return set()
    return {_normalise_curie(entry) for entry in values}


def reset_ontology_tracker() -> None:
    """Clear any cached ontology failure flags between report sections."""
    global _ONTOLOGY_FAILURE
    _ONTOLOGY_FAILURE = False


@dataclass(slots=True)
class FilteredStats:
    improved_granularity: int = 0
    exact_match: int = 0
    regression: int = 0
    no_match_found: int = 0
    other: int = 0
    total_filtered: int = 0
    excluded_broad: int = 0
    ontology_available: bool = True


@dataclass(slots=True)
class RawStats:
    total_annotations: int = 0
    improved: int = 0
    identical: int = 0
    less_specific: int = 0
    no_match: int = 0
    other: int = 0
    ontology_available: bool = True


@dataclass(slots=True)
class ImprovedExample:
    dataset: str
    annotation_text: str
    author_mapping: str
    agent_mapping: str
    enrichment: str


def compute_filtered_stats(
    datasets: Mapping[str, pd.DataFrame],
    match_types: MatchTypeResolver,
    cl_adapter: Any | None,
) -> FilteredStats:
    stats = FilteredStats(ontology_available=cl_adapter is not None)
    for dataset_name, df in datasets.items():
        match_map = match_types.get_map(dataset_name)
        for _, row in df.iterrows():
            author_cl_id = _clean_str(row.get("cl_id"))
            agent_raw = _clean_str(row.get("grounding_cl_id"))
            annotation = _clean_str(row.get("annotation_text"))

            if not author_cl_id:
                continue

            match_type = match_map.get((annotation, author_cl_id), "unknown")
            if match_type in {"broad_term", "overlaps"}:
                stats.excluded_broad += 1
                continue

            stats.total_filtered += 1

            if (
                not agent_raw
                or agent_raw.lower() == "none"
                or agent_raw.lower() == "nan"
                or "NO MATCH" in agent_raw.upper()
            ):
                stats.no_match_found += 1
                continue

            if author_cl_id == agent_raw:
                stats.exact_match += 1
                continue

            agent_ancestors = _get_ancestors(
                cl_adapter, agent_raw, ["rdfs:subClassOf", "BFO:0000050"]
            )
            if author_cl_id in agent_ancestors:
                stats.improved_granularity += 1
                continue

            author_ancestors = _get_ancestors(
                cl_adapter, author_cl_id, ["rdfs:subClassOf"]
            )
            if agent_raw in author_ancestors:
                stats.regression += 1
                continue

            stats.other += 1
    global _ONTOLOGY_FAILURE
    if _ONTOLOGY_FAILURE:
        stats.ontology_available = False
    return stats


def compute_raw_stats(
    datasets: Mapping[str, pd.DataFrame],
    cl_adapter: Any | None,
) -> RawStats:
    stats = RawStats(ontology_available=cl_adapter is not None)
    for df in datasets.values():
        for _, row in df.iterrows():
            author_id = _clean_str(row.get("cl_id"))
            agent_id = _clean_str(row.get("grounding_cl_id"))
            stats.total_annotations += 1

            if not author_id or not agent_id:
                stats.other += 1
                continue

            if "NO MATCH" in agent_id.upper():
                stats.no_match += 1
                continue

            if author_id == agent_id:
                stats.identical += 1
                continue

            if "CL:" in author_id and "CL:" in agent_id:
                agent_ancestors = _get_ancestors(
                    cl_adapter, agent_id, ["rdfs:subClassOf", "BFO:0000050"]
                )
                if author_id in agent_ancestors:
                    stats.improved += 1
                    continue

                author_ancestors = _get_ancestors(
                    cl_adapter, author_id, ["rdfs:subClassOf"]
                )
                if agent_id in author_ancestors:
                    stats.less_specific += 1
                    continue

            stats.other += 1
    global _ONTOLOGY_FAILURE
    if _ONTOLOGY_FAILURE:
        stats.ontology_available = False
    return stats


def collect_improved_examples(
    datasets: Mapping[str, pd.DataFrame],
    cl_adapter: Any | None,
) -> list[ImprovedExample]:
    if cl_adapter is None:
        return []

    examples: list[ImprovedExample] = []
    for dataset_name, df in datasets.items():
        for _, row in df.iterrows():
            author_cl_id = _clean_str(row.get("cl_id"))
            agent_cl_id = _clean_str(row.get("grounding_cl_id"))
            if not author_cl_id or not agent_cl_id or author_cl_id == agent_cl_id:
                continue

            agent_ancestors = _get_ancestors(
                cl_adapter, agent_cl_id, ["rdfs:subClassOf", "BFO:0000050"]
            )
            if author_cl_id in agent_ancestors:
                author_label = _clean_str(row.get("cl_label")) or author_cl_id
                agent_label = _clean_str(row.get("grounding_cl_label")) or agent_cl_id
                enrichment = row.get("enrichment")
                enrichment_str = "" if pd.isna(enrichment) else str(enrichment)

                examples.append(
                    ImprovedExample(
                        dataset=dataset_name,
                        annotation_text=_clean_str(row.get("annotation_text")),
                        author_mapping=f"{author_label} ({author_cl_id})",
                        agent_mapping=f"{agent_label} ({agent_cl_id})",
                        enrichment=enrichment_str,
                    )
                )
    return examples
