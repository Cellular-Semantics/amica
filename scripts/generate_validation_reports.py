#!/usr/bin/env python
"""CLI entrypoint for CXG validation/report generation."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from amica import bootstrap
from amica.validation_reporting import generate_reports


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize CXG grounding outputs using validation reports."
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        help="Base directory containing output/, input/, and reports/. Defaults to the CXG layout output directory.",
    )
    parser.add_argument(
        "--raw-output-dir",
        type=Path,
        help="Direct path to the raw_output directory (overrides --output-root).",
    )
    parser.add_argument(
        "--match-type-dir",
        type=Path,
        help="Direct path to the Pandasaurus match-type directory (overrides --output-root).",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        help="Directory to write markdown reports (defaults to <output-root>/reports).",
    )
    parser.add_argument(
        "--skip-filtered",
        action="store_true",
        help="Skip generating the filtered granularity report.",
    )
    parser.add_argument(
        "--skip-examples",
        action="store_true",
        help="Skip generating the improved examples report.",
    )
    parser.add_argument(
        "--skip-raw-stats",
        action="store_true",
        help="Skip generating the raw aggregate stats report.",
    )
    parser.add_argument(
        "--skip-ontology",
        action="store_true",
        help="Disable ontology lookups (runs offline but degrades improved/regression counts).",
    )
    parser.add_argument(
        "--ontology-adapter",
        help="Override the oaklib adapter spec (ex: 'ols:cl', 'pronto:/path/to/cl.owl').",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity.",
    )
    return parser.parse_args(argv)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def main() -> None:
    args = parse_args()
    configure_logging(args.log_level)
    bootstrap()
    try:
        written = generate_reports(
            include_filtered=not args.skip_filtered,
            include_examples=not args.skip_examples,
            include_raw_stats=not args.skip_raw_stats,
            output_root=args.output_root,
            raw_output_dir=args.raw_output_dir,
            match_type_dir=args.match_type_dir,
            reports_dir=args.reports_dir,
            skip_ontology=args.skip_ontology,
            adapter_spec=args.ontology_adapter,
        )
        if not written:
            logging.warning("No reports were generated (all sections skipped).")
    except Exception as exc:  # pragma: no cover - CLI
        logging.error("Validation reporting failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
