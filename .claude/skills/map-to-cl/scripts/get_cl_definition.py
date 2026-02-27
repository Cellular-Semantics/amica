#!/usr/bin/env python3
"""Fetch the OAK definition text for a Cell Ontology term.

Usage:
    uv run python scripts/get_cl_definition.py CL:0009042

Output (stdout):
    The definition string from the ontology, or a message if not found.

Uses the OLS adapter by default. Set CL_ADAPTER env var to override,
e.g. CL_ADAPTER=pronto:cl.obo for fast local iteration.
"""
from __future__ import annotations

import os
import sys

from oaklib import get_adapter


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: get_cl_definition.py <CL:ID>", file=sys.stderr)
        sys.exit(1)

    cl_id = sys.argv[1]
    adapter_name = os.environ.get("CL_ADAPTER", "ols:cl")

    adapter = get_adapter(adapter_name)

    try:
        defn = adapter.definition(cl_id)
    except Exception as exc:  # noqa: BLE001
        print(f"# Error fetching definition for {cl_id}: {exc}", file=sys.stderr)
        sys.exit(1)

    if defn:
        print(defn)
    else:
        print(f"# No definition found for {cl_id}", file=sys.stderr)


if __name__ == "__main__":
    main()
