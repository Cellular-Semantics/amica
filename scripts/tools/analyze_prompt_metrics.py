"""Aggregate prompt_metrics logs for expansion and grounding runs."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

KIND_EXPANSION = "expansion"
KIND_GROUNDING = "grounding"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize prompt_metrics logs produced by AMICA services.",
    )
    parser.add_argument(
        "logfile",
        type=Path,
        help="Path to the log file containing prompt_metrics entries.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write aggregated JSON stats (defaults to stdout).",
    )
    return parser.parse_args()


def parse_prompt_metrics(line: str) -> dict[str, Any] | None:
    if "prompt_metrics" not in line:
        return None
    try:
        _, payload = line.split("prompt_metrics", 1)
        return json.loads(payload.strip())
    except (ValueError, json.JSONDecodeError):
        return None


def summarize(log_path: Path) -> dict[str, Any]:
    stats: dict[str, dict[str, Any]] = {
        KIND_EXPANSION: {
            "articles": set(),
            "total_original_tokens": 0,
            "total_context_tokens": 0,
            "samples": 0,
        },
        KIND_GROUNDING: {
            "articles": set(),
            "total_context_chars": 0,
            "samples": 0,
        },
    }

    for line in log_path.read_text().splitlines():
        payload = parse_prompt_metrics(line)
        if not payload:
            continue
        kind = payload.get("kind", KIND_EXPANSION)
        if kind == KIND_EXPANSION:
            entry = stats[KIND_EXPANSION]
            entry["articles"].add(payload.get("article_id"))
            entry["total_original_tokens"] += payload.get("original_tokens", 0)
            entry["total_context_tokens"] += payload.get("context_tokens", 0)
            entry["samples"] += 1
        elif kind == KIND_GROUNDING:
            entry = stats[KIND_GROUNDING]
            entry["articles"].add(payload.get("article_id"))
            entry["total_context_chars"] += payload.get("context_chars", 0)
            entry["samples"] += 1

    # Convert sets to counts and compute ratios
    exp = stats[KIND_EXPANSION]
    grd = stats[KIND_GROUNDING]
    exp["articles"] = len(exp["articles"])  # type: ignore[assignment]
    grd["articles"] = len(grd["articles"])  # type: ignore[assignment]
    if exp["samples"] and exp["total_original_tokens"]:
        exp["avg_reduction"] = 1 - (
            exp["total_context_tokens"] / exp["total_original_tokens"]
        )
    return stats


def main() -> None:
    args = parse_args()
    if not args.logfile.exists():
        raise FileNotFoundError(args.logfile)

    stats = summarize(args.logfile)
    payload = json.dumps(stats, indent=2)
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload)

if __name__ == "__main__":
    main()
