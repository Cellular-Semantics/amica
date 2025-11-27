"""Global configuration helpers for AMICA workflows."""

from __future__ import annotations

from typing import Tuple

from amica.utils.cxg import CxgPipelineSettings, CxgResourceLayout


def load_cxg_configuration() -> Tuple[CxgPipelineSettings, CxgResourceLayout]:
    """Load CXG pipeline settings/layout from environment variables."""
    settings = CxgPipelineSettings.from_env()
    layout = CxgResourceLayout.from_env()
    return settings, layout


__all__ = ["load_cxg_configuration"]
