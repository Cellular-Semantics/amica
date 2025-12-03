"""
Tools for the Paper Cell Type Agent.
"""

import json
import logging
from typing import Any

import fitz
from pydantic_ai import RunContext

logger = logging.getLogger(__name__)


def get_full_text(ctx: RunContext[str], pdf_path: str) -> str:
    """
    Get the full text of a PDF file.

    Args:
        ctx: The run context
        pdf_path: The path to the PDF file.

    Returns:
        The full text of the PDF file.
    """
    doc = fitz.open(pdf_path)
    text = "\n".join(page.get_text("text") for page in doc)
    return text


def read_json(ctx: RunContext[str], file_path: str) -> list[dict[str, Any]]:
    """
    Reads and parses a JSON file from the given file path.

    Args:
        file_path: The absolute or relative path to the JSON file.

    Returns:
        The content of the JSON file as a Python dictionary.
        Assumes the JSON contains a list of dictionaries under a 'data' key for 'cc.label'.
    """
    try:
        with open(file_path, encoding="utf-8-sig") as file:
            data = json.load(file)
        if isinstance(data, list) and all(
            isinstance(item, dict) and "cc.label" in item for item in data
        ):
            print(f"Successfully read JSON from {file_path}. Found {len(data)} entries.")
            return data
        raise ValueError(
            "JSON file format not as expected. Expected a list of dictionaries, "
            "each with a 'cc.label'.",
        )
    except FileNotFoundError as err:
        raise FileNotFoundError(f"JSON file not found at: {file_path}") from err
    except json.JSONDecodeError as err:
        raise ValueError(f"Invalid JSON format in file: {file_path}") from err
    except Exception as err:
        raise RuntimeError(f"Error reading JSON file {file_path}: {err}") from err
