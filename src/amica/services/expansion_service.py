"""Expansion service that enriches annotations via the paper cell type agent."""

from __future__ import annotations

import json
import logging
from typing import Dict, List

from amica.agents.paper_celltype.paper_celltype_agent import (
    CellTypeEntry,
    celltype_agent,
)
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

--- Academic Paper Content (extracted from PDF):
{paper_full_text}

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
        agent=celltype_agent,
    ) -> None:
        self.layout = layout
        self.settings = settings or CxgPipelineSettings()
        self.agent = agent

    async def expand_annotations(self, bundle: PreparedAnnotationBundle) -> None:
        dataset_map = self._group_by_dataset_and_article(bundle)
        for dataset_name in bundle.dataset_names:
            dataset_articles = dataset_map.get(dataset_name, {})
            if not dataset_articles:
                continue

            dataset_cache_dir = self.layout.expansions_dir / normalise_identifier(
                dataset_name
            )
            dataset_cache_dir.mkdir(parents=True, exist_ok=True)

            for article_id, annotations in sorted(dataset_articles.items()):
                await self._expand_article_annotations(
                    dataset_name, article_id, annotations, dataset_cache_dir
                )

    async def _expand_article_annotations(
        self,
        dataset_name: str,
        article_id: str,
        annotations: List[AnnotationRecord],
        dataset_cache_dir,
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

        batch_size = self.settings.annotations_batch_size
        for batch_index in range(0, len(annotations), batch_size):
            batch = annotations[batch_index : batch_index + batch_size]
            cache_file = dataset_cache_dir / f"{slug}_batch_{batch_index // batch_size}.json"
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

            await self._generate_and_cache_expansions(
                dataset_name,
                article_id,
                batch,
                article_text,
                cache_file,
            )

    def _hydrate_from_cache(
        self,
        batch: List[AnnotationRecord],
        cached_entries: List[dict],
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
        batch: List[AnnotationRecord],
        article_text: str,
        cache_file,
    ) -> None:
        cc_labels = [{"cc.label": ann.annotation_text} for ann in batch]
        prompt = PROMPT_TEMPLATE.format(
            cc_json=json.dumps(cc_labels, indent=2),
            paper_full_text=article_text,
        )
        logger.info(
            "[%s] Generating expansions for article %s (batch size %s)",
            dataset_name,
            article_id,
            len(batch),
        )
        response = await self.agent.run(prompt)
        annotations = response.output.cell_type_annotations
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
                record.enrichment = entry.model_copy()

        cache_file.write_text(
            json.dumps([entry.model_dump() for entry in annotations], indent=2),
            encoding="utf-8",
        )

    def _group_by_dataset_and_article(
        self, bundle: PreparedAnnotationBundle
    ) -> Dict[str, Dict[str, List[AnnotationRecord]]]:
        dataset_map: Dict[str, Dict[str, List[AnnotationRecord]]] = {}
        for doi, annotations in bundle.article_to_annotations.items():
            for record in annotations:
                dataset_articles = dataset_map.setdefault(record.dataset_name, {})
                dataset_articles.setdefault(doi, []).append(record)
        return dataset_map
