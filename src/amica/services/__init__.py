"""Integration-facing services (LLM clients, Deepsearch, etc.)."""

from __future__ import annotations

from amica.utils.cxg import (
    AnnotationRecord,
    CxgPipelineSettings,
    CxgResourceLayout,
    PreparedAnnotationBundle,
)

from .dataset_loader import DatasetLoader
from .expansion_service import ExpansionService
from .grounding_service import GroundingService
from .publication_fetcher import PublicationFetcher
from .vector_store import (
    DocumentChunk,
    DocumentVectorStore,
    EmbeddingBackend,
    OpenAIEmbeddingBackend,
)

__all__ = [
    "AnnotationRecord",
    "CxgPipelineSettings",
    "CxgResourceLayout",
    "DatasetLoader",
    "PreparedAnnotationBundle",
    "ExpansionService",
    "GroundingService",
    "PublicationFetcher",
    "DocumentChunk",
    "DocumentVectorStore",
    "EmbeddingBackend",
    "OpenAIEmbeddingBackend",
]
