"""Tooling helpers exposed to the annotator agent."""

from __future__ import annotations

import logging

from oaklib import get_adapter
from pydantic_ai import RunContext

from .annotator_config import AnnotatorDependencies

logger = logging.getLogger(__name__)


def search_cl(
    ctx: RunContext[AnnotatorDependencies], term: str, /
) -> list[tuple[str, str]]:
    """
    Search the Cell Ontology for a term and return CL identifier/label pairs.

    Note that search should take into account synonyms, but synonyms may be incomplete,
    so if you cannot find a concept of interest, try searching using related or synonymous
    terms.

    Args:
        ctx: The run context (unused, but required by the tool signature)
        term: The term to search for.

    Returns:
        A list of tuples, each containing a CL ID and a label.
    """
    adapter = get_adapter("ols:cl")
    results = adapter.basic_search(term)
    labels = list(adapter.labels(results))
    logger.debug("CL search query='%s' results=%s", term, labels)
    return labels
