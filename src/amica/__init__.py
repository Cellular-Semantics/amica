from __future__ import annotations

from typing import Optional

from dotenv import load_dotenv


def bootstrap(dotenv_path: str | None = None) -> None:
    """Load environment configuration required for agent workflows.

    Call this once at application startup. If dotenv_path is provided, that file is loaded;
    otherwise load_dotenv() will search default locations.
    """
    if dotenv_path:
        load_dotenv(dotenv_path)
    else:
        load_dotenv()