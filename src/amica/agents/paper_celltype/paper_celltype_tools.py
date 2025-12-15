"""Tools for the Paper Cell Type Agent."""

from __future__ import annotations

import json
import logging
from typing import Any

import fitz
from pydantic_ai import RunContext

from amica.services.vector_store import DocumentVectorStore, OpenAIEmbeddingBackend
from amica.utils.cxg import CxgPipelineSettings, CxgResourceLayout
from amica.agents.paper_celltype.paper_celltype_config import PaperCTDependencies

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
            print(
                f"Successfully read JSON from {file_path}. Found {len(data)} entries."
            )
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


def search_cached_snippets(
    ctx: RunContext[PaperCTDependencies],
    /,
    doi: str,
    query: str,
    *,
    top_k: int = 3,
) -> list[str]:
    """Return cached article snippets similar to ``query`` using the vector store."""

    store = _get_vector_store()
    if not store:
        logger.debug("Vector store not configured; search_cached_snippets returning []")
        return []

    try:
        results = store.similarity_search(doi, query, top_k=top_k)
        return [chunk.text for chunk in results]
    except Exception as exc:
        logger.warning("Vector store search failed for %s: %s", doi, exc)
        return []


_VECTOR_STORE: DocumentVectorStore | None = None


def _get_vector_store() -> DocumentVectorStore | None:
    global _VECTOR_STORE
    if _VECTOR_STORE is not None:
        return _VECTOR_STORE

    settings = CxgPipelineSettings.from_env()
    if not settings.vector_store_enabled:
        return None

    layout = CxgResourceLayout.from_env()
    try:
        backend = OpenAIEmbeddingBackend(model_name=settings.embedding_model)
        _VECTOR_STORE = DocumentVectorStore(
            layout,
            backend=backend,
            chunk_chars=settings.chunk_chars,
            chunk_overlap=settings.chunk_overlap,
        )
    except Exception as exc:  # pragma: no cover - network/env dependent
        logger.warning("Vector store unavailable in agent tools: %s", exc)
        _VECTOR_STORE = None
    return _VECTOR_STORE
