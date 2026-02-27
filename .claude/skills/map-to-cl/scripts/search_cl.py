#!/usr/bin/env python3
"""Search the Cell Ontology for a term and print ranked results.

Usage:
    uv run python scripts/search_cl.py "colonic enteroendocrine cell"

Output (TSV, stdout):
    cl_id\tcl_label

Uses the OLS adapter by default. Set CL_ADAPTER env var to override,
e.g. CL_ADAPTER=pronto:cl.obo for fast local iteration.
"""
from __future__ import annotations

import os
import sys

from oaklib import get_adapter


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: search_cl.py <term>", file=sys.stderr)
        sys.exit(1)

    term = sys.argv[1]
    adapter_name = os.environ.get("CL_ADAPTER", "ols:cl")

    adapter = get_adapter(adapter_name)
    results = list(adapter.basic_search(term))

    if not results:
        print(f"# No results for: {term}", file=sys.stderr)
        sys.exit(0)

    labels = list(adapter.labels(results))
    for cl_id, label in labels:
        print(f"{cl_id}\t{label}")


if __name__ == "__main__":
    main()
