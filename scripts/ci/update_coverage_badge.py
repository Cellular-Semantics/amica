#!/usr/bin/env python3
"""Generate Shields.io coverage badge data from coverage.xml."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from xml.etree import ElementTree

COVERAGE_XML = Path("coverage.xml")
BADGE_PATH = Path(".github/badges/coverage.json")


def coverage_color(percent: float) -> str:
    """Map coverage percentage to a Shields.io-friendly color."""
    if percent >= 90:
        return "brightgreen"
    if percent >= 80:
        return "green"
    if percent >= 70:
        return "yellowgreen"
    if percent >= 60:
        return "yellow"
    if percent >= 40:
        return "orange"
    return "red"


def main() -> int:
    if not COVERAGE_XML.exists():
        print(
            f"coverage.xml not found at {COVERAGE_XML}. "
            "Run `uv run pytest --cov=src/amica --cov-report=xml` first.",
            file=sys.stderr,
        )
        return 1

    root = ElementTree.parse(COVERAGE_XML).getroot()
    line_rate = root.attrib.get("line-rate")
    if line_rate is None:
        print("coverage.xml missing 'line-rate' attribute", file=sys.stderr)
        return 1

    percent = float(line_rate) * 100
    BADGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BADGE_PATH.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "label": "coverage",
                "message": f"{percent:.1f}%",
                "color": coverage_color(percent),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote coverage badge with {percent:.1f}% coverage to {BADGE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
