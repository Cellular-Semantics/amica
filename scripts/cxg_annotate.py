#!/usr/bin/env python
"""CLI entrypoint for the CXG annotation workflow."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from amica import bootstrap
from amica.graphs import run_cxg_workflow
from amica.utils.cxg import (
    CxgPipelineSettings,
    CxgResourceLayout,
    load_cxg_configuration,
)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments for the CXG annotation workflow.

    Args:
        argv: Override for argument list, primarily used in tests.

    Returns:
        Parsed :class:`argparse.Namespace` populated with CLI options.
    """
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
        "--enable-vector-store",
        action="store_true",
        help="Enable retrieval-augmented prompting via the vector store.",
    )
    parser.add_argument(
        "--embedding-model",
        type=str,
        help="Embedding model to use when building the vector store.",
    )
    parser.add_argument(
        "--chunk-chars",
        type=int,
        help="Maximum characters per chunk when indexing publication text.",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        help="Number of overlapping characters between consecutive chunks.",
    )
    parser.add_argument(
        "--retrieval-top-k",
        type=int,
        help="Number of retrieved snippets to inject into each prompt batch.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity.",
    )
    return parser.parse_args(argv)


def configure_logging(level: str) -> None:
    """Configure root logging for the CLI.

    Args:
        level: Logging level name provided on the CLI.
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


async def _async_main(args: argparse.Namespace) -> None:
    """Async entrypoint that wires CLI args into the CXG workflow.

    Args:
        args: Parsed CLI arguments produced by :func:`parse_args`.
    """
    bootstrap()
    settings, layout = load_cxg_configuration()
    if args.batch_size is not None:
        settings.annotations_batch_size = args.batch_size
    if args.test_mode:
        settings.test_mode = True
    if args.test_annotations_count is not None:
        settings.test_annotations_count = args.test_annotations_count
    if args.enable_vector_store:
        settings.vector_store_enabled = True
    if args.embedding_model is not None:
        settings.embedding_model = args.embedding_model
    if args.chunk_chars is not None:
        settings.chunk_chars = args.chunk_chars
    if args.chunk_overlap is not None:
        settings.chunk_overlap = args.chunk_overlap
    if args.retrieval_top_k is not None:
        settings.retrieval_top_k = args.retrieval_top_k
    if args.resources_dir is not None:
        layout = CxgResourceLayout(resources_dir=args.resources_dir)

    os.environ["CXG_RESOURCES_DIR"] = str(layout.resources_dir)
    os.environ["CXG_VECTOR_STORE_ENABLED"] = "1" if settings.vector_store_enabled else "0"
    os.environ["CXG_EMBEDDING_MODEL"] = settings.embedding_model
    os.environ["CXG_CHUNK_CHARS"] = str(settings.chunk_chars)
    os.environ["CXG_CHUNK_OVERLAP"] = str(settings.chunk_overlap)
    os.environ["CXG_RETRIEVAL_TOP_K"] = str(settings.retrieval_top_k)

    await run_cxg_workflow(settings=settings, layout=layout)


def main() -> None:
    """CLI entrypoint that executes the CXG workflow."""
    args = parse_args()
    configure_logging(args.log_level)
    try:
        asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
