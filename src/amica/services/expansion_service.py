"""Expansion service that enriches annotations via the paper cell type agent."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Iterable

# try:
from tiktoken import encoding_for_model
# except ImportError:  # pragma: no cover - tokenizer is optional
# encoding_for_model = None  # type: ignore

from pydantic_ai import Agent
from pydantic_ai.agent import AgentRunResult

from amica.agents.paper_celltype.paper_celltype_agent import (
    BiocurationOutput,
    CellTypeEntry,
    celltype_agent,
)
from amica.agents.paper_celltype.paper_celltype_config import PaperCTDependencies
from amica.services.vector_store import DocumentVectorStore
from amica.utils.cxg import (
    AnnotationRecord,
    CxgPipelineSettings,
    CxgResourceLayout,
    PreparedAnnotationBundle,
    normalise_identifier,
)

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """
You are tasked with extracting cell type information from the provided academic paper content,
and the provided JSON data.

The JSON contains cell type annotations (cc.label column) from single-cell transcriptomic data.

Based on the following JSON data and academic paper content, generate a list of structured
cell type entries. Each entry must follow the `CellTypeEntry` schema.

--- JSON List Input Data:
{cc_json}

--- Article Context (retrieved excerpts or fallback text):
{article_context}

--- COLUMN DEFINITIONS AND LOGIC:
- `name`: The exact `cc.label` from the input JSON.
- `full_name`: Use the following logic:
    1. If the full label (e.g., "SI_TA") is defined directly in the paper, use the exact definition.
    2. If not, check if individual parts (e.g., prefixes, suffixes) are defined and reconstruct/assemble the `full_name` from the parts found.
    3. If the label begins with a defined prefix abbreviation, expand the prefix and append the remaining label.
    4. If only one part is defined, use just that part.
    5. If no parts are defined, leave this field blank.
- `paper_synonyms`: Use only synonyms mentioned in the paper via abbreviation lists or explicit synonym statements. Separate entries with semicolons (;).
- `tissue_context`: Exact quoted tissue(s) or anatomical terms from the paper where the cell type was identified.

Process all `cc.label` entries from the JSON data automatically.
Do not ask for confirmation.
Provide the output as a JSON array of `CellTypeEntry` objects.
"""


class ExpansionService:
    """Populate `enrichment` fields on annotation records using the celltype agent."""

    def __init__(
        self,
        layout: CxgResourceLayout,
        settings: CxgPipelineSettings | None = None,
        agent: Agent[PaperCTDependencies, BiocurationOutput] = celltype_agent,
        vector_store: DocumentVectorStore | None = None,
        retrieval_top_k: int = 2,
    ) -> None:
        self.layout = layout
        self.settings = settings or CxgPipelineSettings()
        self.agent = agent
        self.vector_store = vector_store
        self.retrieval_top_k = retrieval_top_k
        self._snippet_cache: dict[tuple[str, str], list[str]] = {}
        self._tokenize_cache: Callable[[str], int] | None = None

    async def expand_annotations(self, bundle: PreparedAnnotationBundle) -> None:
        """Populate enrichment metadata for each annotation in the bundle.

        Args:
            bundle: Prepared annotations grouped by dataset/article.
        """
        dataset_map = self._group_by_dataset_and_article(bundle)
        for dataset_name in bundle.dataset_names:
            dataset_articles = dataset_map.get(dataset_name, {})
            if not dataset_articles:
                continue

            dataset_cache_dir = self.layout.expansions_dir / normalise_identifier(
                dataset_name
            )
            dataset_cache_dir.mkdir(parents=True, exist_ok=True)

            for article_id, article_annotations in sorted(dataset_articles.items()):
                await self._expand_article_annotations(
                    dataset_name, article_id, article_annotations, dataset_cache_dir
                )

    async def _expand_article_annotations(
        self,
        dataset_name: str,
        article_id: str,
        article_annotations: list[AnnotationRecord],
        dataset_cache_dir: Path,
    ) -> None:
        logger.info("[%s] Expanding entries for article %s", dataset_name, article_id)
        slug = normalise_identifier(article_id or "unknown")
        article_path = self.layout.publications_dir / f"{slug}.txt"

        if not article_path.exists():
            logger.warning(
                "[%s] Missing publication text for article %s; skipping expansion",
                dataset_name,
                article_id,
            )
            return

        article_text = article_path.read_text(encoding="utf-8")
        if self.vector_store:
            self.vector_store.ensure_index(article_id, article_text)

        batch_size = self.settings.annotations_batch_size
        for batch_index in range(0, len(article_annotations), batch_size):
            batch = article_annotations[batch_index : batch_index + batch_size]
            cache_file = (
                dataset_cache_dir / f"{slug}_batch_{batch_index // batch_size}.json"
            )
            if cache_file.exists():
                logger.debug(
                    "[%s] Using cached expansion batch %s for article %s",
                    dataset_name,
                    batch_index // batch_size,
                    article_id,
                )
                cached_entries = json.loads(cache_file.read_text(encoding="utf-8"))
                self._hydrate_from_cache(batch, cached_entries)
                continue

            article_context = self._build_article_context(
                article_id, batch, article_text
            )

            await self._generate_and_cache_expansions(
                dataset_name,
                article_id,
                batch,
                article_context,
                cache_file,
            )

    def _hydrate_from_cache(
        self,
        batch: list[AnnotationRecord],
        cached_entries: list[dict],
    ) -> None:
        by_name = {record.annotation_text: record for record in batch}
        for entry in cached_entries:
            cell_entry = CellTypeEntry(**entry)
            record = by_name.get(cell_entry.name)
            if record:
                record.enrichment = cell_entry.model_dump()

    async def _generate_and_cache_expansions(
        self,
        dataset_name: str,
        article_id: str,
        batch: list[AnnotationRecord],
        article_context: str,
        cache_file: Path,
    ) -> None:
        cc_labels = [{"cc.label": ann.annotation_text} for ann in batch]
        prompt = PROMPT_TEMPLATE.format(
            cc_json=json.dumps(cc_labels, indent=2),
            article_context=article_context,
        )
        logger.info(
            "[%s] Generating expansions for article %s (batch size %s)",
            dataset_name,
            article_id,
            len(batch),
        )
        result = await self.agent.run(prompt)
        self._log_agent_usage(
            kind="expansion",
            dataset_name=dataset_name,
            article_id=article_id,
            batch_size=len(batch),
            run_result=result,
        )
        annotations = result.output.cell_type_annotations
        by_name = {record.annotation_text: record for record in batch}

        for entry in annotations:
            logger.debug(
                "[%s] Expansion result: %s -> %s",
                dataset_name,
                entry.name,
                entry.full_name,
            )
            record = by_name.get(entry.name)
            if record:
                record.enrichment = entry.model_dump()

        cache_file.write_text(
            json.dumps([entry.model_dump() for entry in annotations], indent=2),
            encoding="utf-8",
        )

    def _group_by_dataset_and_article(
        self, bundle: PreparedAnnotationBundle
    ) -> dict[str, dict[str, list[AnnotationRecord]]]:
        dataset_map: dict[str, dict[str, list[AnnotationRecord]]] = {}
        for doi, article_annotations in bundle.article_to_annotations.items():
            for record in article_annotations:
                dataset_articles = dataset_map.setdefault(record.dataset_name, {})
                dataset_articles.setdefault(doi, []).append(record)
        return dataset_map

    def _build_article_context(
        self,
        article_id: str,
        batch: Iterable[AnnotationRecord],
        fallback_text: str,
    ) -> str:
        if not self.vector_store:
            return fallback_text

        snippets: list[str] = []
        seen: set[str] = set()
        for record in batch:
            query = (record.annotation_text or "").strip()
            if not query:
                continue
            cache_key = (article_id, query)
            cached = self._snippet_cache.get(cache_key)
            if cached is None:
                matches = self.vector_store.similarity_search(
                    article_id,
                    query,
                    top_k=self.retrieval_top_k,
                )
                texts = [chunk.text.strip() for chunk in matches if chunk.text.strip()]
                self._snippet_cache[cache_key] = texts
            else:
                texts = cached

            for text in texts:
                if text and text not in seen:
                    seen.add(text)
                    snippets.append(text)

        if snippets:
            context = "\n\n".join(snippets)
            self._log_prompt_metrics(article_id, fallback_text, context)
        else:
            context = fallback_text

        return context

    def _log_prompt_metrics(
        self,
        article_id: str,
        original_text: str,
        context_text: str,
    ) -> None:
        original_chars = len(original_text)
        context_chars = len(context_text)
        payload = {
            "article_id": article_id,
            "original_chars": original_chars,
            "context_chars": context_chars,
        }
        tokenizer = self._get_tokenizer()
        if tokenizer:
            payload["original_tokens"] = tokenizer(original_text)
            payload["context_tokens"] = tokenizer(context_text)
        logger.debug("prompt_metrics %s", json.dumps(payload))

    def _log_agent_usage(
        self,
        *,
        kind: str,
        dataset_name: str,
        article_id: str,
        batch_size: int,
        run_result: AgentRunResult[Any],
    ) -> None:
        usage = None
        try:
            usage = run_result.usage()
        except Exception:  # pragma: no cover - defensive
            usage = None
        if not usage:
            return
        payload = {
            "kind": kind,
            "dataset": dataset_name,
            "article_id": article_id,
            "batch_size": batch_size,
            "usage": asdict(usage),
        }
        logger.info("openai_usage %s", json.dumps(payload))

    def _get_tokenizer(self) -> Callable[[str], int] | None:
        if not getattr(self, "_tokenize_cache", None):
            if encoding_for_model is None:
                self._tokenize_cache = None
            else:
                try:
                    encoding = encoding_for_model(self.settings.embedding_model)

                    def _encode(text: str) -> int:
                        return len(encoding.encode(text))

                    self._tokenize_cache = _encode
                except Exception:  # pragma: no cover - best effort
                    self._tokenize_cache = None
        return self._tokenize_cache
