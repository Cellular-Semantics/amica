"""Shared pytest configuration and path fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

# Make scripts/ importable so tests can exercise CLI helpers like parse_args.
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
