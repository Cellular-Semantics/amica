#!/usr/bin/env python3
"""Get all CL terms with an inferred part_of or located_in relationship to a tissue.

Uses the ubergraph adapter which has pre-computed transitive closures across
CL and UBERON.

Usage:
    uv run python scripts/filter_by_tissue.py kidney
    uv run python scripts/filter_by_tissue.py "UBERON:0002113"

Output (stdout):
    One CL ID per line.

The output can be used to filter/rank search_cl.py results: prefer candidates
whose CL ID appears in this list.

Tissue argument accepts:
  - A plain tissue name (e.g. "kidney") → looked up via basic_search on UBERON
  - A UBERON CURIE (e.g. "UBERON:0002113") → used directly

Results are cached to /tmp/filter_by_tissue_{tissue}.txt to avoid repeated
ubergraph calls within a session.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PART_OF = "BFO:0000050"
LOCATED_IN = "RO:0001025"


def resolve_uberon_id(tissue: str, adapter) -> str | None:
    """Return UBERON CURIE for a tissue name, or pass through if already a CURIE."""
    if re.match(r"^UBERON:\d+$", tissue):
        return tissue
    results = list(adapter.basic_search(tissue, code="UBERON"))
    if not results:
        # Try without ontology restriction
        results = [r for r in adapter.basic_search(tissue) if r.startswith("UBERON:")]
    return results[0] if results else None


def get_tissue_cl_ids(tissue: str) -> list[str]:
    """Return all CL IDs inferred to be part_of or located_in the given tissue."""
    cache_key = re.sub(r"[^a-zA-Z0-9]", "_", tissue)
    cache_path = Path(f"/tmp/filter_by_tissue_{cache_key}.txt")

    if cache_path.exists():
        return cache_path.read_text().splitlines()

    from oaklib import get_adapter

    adapter = get_adapter("ubergraph:")

    uberon_id = resolve_uberon_id(tissue, adapter)
    if not uberon_id:
        print(f"# Could not resolve tissue '{tissue}' to a UBERON ID", file=sys.stderr)
        return []

    cl_ids: set[str] = set()
    for predicate in [PART_OF, LOCATED_IN]:
        try:
            rels = adapter.relationships(
                predicates=[predicate],
                objects=[uberon_id],
            )
            for subj, _pred, _obj in rels:
                if subj.startswith("CL:"):
                    cl_ids.add(subj)
        except Exception as exc:  # noqa: BLE001
            print(f"# Warning: relationship query failed ({predicate}): {exc}", file=sys.stderr)

    result = sorted(cl_ids)
    cache_path.write_text("\n".join(result))
    return result


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: filter_by_tissue.py <tissue-name-or-uberon-id>", file=sys.stderr)
        sys.exit(1)

    tissue = " ".join(sys.argv[1:])
    cl_ids = get_tissue_cl_ids(tissue)

    if not cl_ids:
        print(f"# No CL terms found for tissue: {tissue}", file=sys.stderr)
        sys.exit(0)

    for cl_id in cl_ids:
        print(cl_id)


if __name__ == "__main__":
    main()
