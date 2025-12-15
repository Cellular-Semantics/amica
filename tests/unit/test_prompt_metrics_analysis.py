from __future__ import annotations

import pytest

import importlib.util
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "tools"
    / "analyze_prompt_metrics.py"
)
_SPEC = importlib.util.spec_from_file_location("analyze_prompt_metrics", _MODULE_PATH)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
parse_prompt_metrics = _MODULE.parse_prompt_metrics
summarize = _MODULE.summarize

pytestmark = pytest.mark.unit


def test_parse_prompt_metrics_handles_valid_line():
    line = '2024 INFO prompt_metrics {"article_id": "A", "kind": "expansion"}'
    payload = parse_prompt_metrics(line)
    assert payload == {"article_id": "A", "kind": "expansion"}


def test_summarize_aggregates(tmp_path):
    log_text = "\n".join(
        [
            'prompt_metrics {"kind": "expansion", "article_id": "A", "original_tokens": 100, "context_tokens": 40}',
            'prompt_metrics {"kind": "grounding", "article_id": "A", "context_chars": 20}',
        ]
    )
    log_file = tmp_path / "metrics.log"
    log_file.write_text(log_text, encoding="utf-8")

    stats = summarize(log_file)
    assert stats["expansion"]["samples"] == 1
    assert stats["grounding"]["samples"] == 1
    assert stats["grounding"]["total_context_chars"] == 20
    assert pytest.approx(stats["expansion"]["avg_reduction"], rel=1e-6) == 0.6
