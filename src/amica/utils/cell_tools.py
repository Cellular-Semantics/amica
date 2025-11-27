"""
Tools for the Cell agent.
"""
import os
import logging
from typing import List, Tuple

from oaklib import get_adapter
from pydantic_ai import RunContext

logger = logging.getLogger(__name__)


def search_cl(ctx: RunContext[str], term: str) -> List[Tuple[str, str]]:
    """
    Search the cl ontology for a term.

    Note that search should take into account synonyms, but synonyms may be incomplete,
    so if you cannot find a concept of interest, try searching using related or synonymous
    terms.

    If you are searching for a composite term, try searching on the sub-terms to get a sense
    of the terminology used in the ontology.

    Args:
        ctx: The run context
        term: The term to search for.

    Returns:
        A list of tuples, each containing a CL ID and a label.
    """
    adapter = get_adapter("ols:cl")
    results = adapter.basic_search(term)
    labels = list(adapter.labels(results))
    print(f"## Query: {term} -> {labels}")
    return labels