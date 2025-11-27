#!/usr/bin/env python
"""CLI entrypoint for the CXG annotation workflow."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

from amica import bootstrap
from amica.config import load_cxg_configuration
from amica.graphs import run_cxg_workflow
from amica.utils.cxg import CxgPipelineSettings, CxgResourceLayout


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the CXG annotation workflow against local datasets."
    )
    parser.add_argument(
        "--resources-dir",
        type=Path,
        help="Override the base resources directory (default pulled from CXG_RESOURCES_DIR or resources/cxg).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        help="Override the annotations batch size used for expansions/grounding.",
    )
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Enable test mode (truncates annotations).",
    )
    parser.add_argument(
        "--test-annotations-count",
        type=int,
        help="Number of annotations to process when test mode is enabled.",
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


async def _async_main(args: argparse.Namespace) -> None:
    bootstrap()
    settings, layout = load_cxg_configuration()
    if args.batch_size is not None:
        settings.annotations_batch_size = args.batch_size
    if args.test_mode:
        settings.test_mode = True
    if args.test_annotations_count is not None:
        settings.test_annotations_count = args.test_annotations_count
    if args.resources_dir is not None:
        layout = CxgResourceLayout(resources_dir=args.resources_dir)

    await run_cxg_workflow(settings=settings, layout=layout)


def main() -> None:
    args = parse_args()
    configure_logging(args.log_level)
    try:
        asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
