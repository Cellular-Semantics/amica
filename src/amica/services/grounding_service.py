"""Ground annotation enrichments against the Cell Ontology."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from amica.agents.annotator.annotator_agent import (
    TextAnnotation,
    TextAnnotationResult,
    annotator_agent,
)
from amica.agents.paper_celltype.paper_celltype_agent import CellTypeEntry
from amica.utils.cxg import (
    AnnotationRecord,
    CxgPipelineSettings,
    CxgResourceLayout,
    PreparedAnnotationBundle,
    normalise_identifier,
)

logger = logging.getLogger(__name__)


class GroundingService:
    """Batch grounding service backed by the ontology annotator agent."""

    def __init__(
        self,
        layout: CxgResourceLayout,
        settings: CxgPipelineSettings | None = None,
        agent=annotator_agent,
    ) -> None:
        self.layout = layout
        self.settings = settings or CxgPipelineSettings()
        self.agent = agent

    async def ground_annotations(self, bundle: PreparedAnnotationBundle) -> None:
        """Ground enriched annotations against the Cell Ontology and persist reports.

        Args:
            bundle: Prepared annotation bundle mutated in-place with CL grounding.
        """
        annotations = list(bundle.annotations)
        logger.info("Grounding %s annotations", len(annotations))
        self._normalise_enrichment_state(annotations)

        grouped = self._group_by_dataset(annotations)
        self.layout.cache_dir.mkdir(parents=True, exist_ok=True)

        for dataset_name in bundle.dataset_names:
            dataset_annotations = grouped.get(dataset_name, [])
            if not dataset_annotations:
                continue
            cache_dir = self.layout.cache_dir / normalise_identifier(dataset_name)
            cache_dir.mkdir(parents=True, exist_ok=True)
            await self._process_dataset(dataset_name, dataset_annotations, cache_dir)

        self._write_reports(bundle)

    def _normalise_enrichment_state(self, annotations: Sequence[AnnotationRecord]) -> None:
        for record in annotations:
            if not record.enrichment or isinstance(record.enrichment, dict):
                record.enrichment = CellTypeEntry(
                    name=record.annotation_text,
                    full_name="",
                    paper_synonyms="",
                    tissue_context="",
                )
            else:
                record.enrichment.tissue_context = ""
            record.grounding_cl_id = None
            record.grounding_cl_label = None

        annotations.sort(
            key=lambda rec: (
                rec.article_id_doi or "",
                rec.annotation_text or "",
            )
        )

    async def _process_dataset(
        self,
        dataset_name: str,
        annotations: list[AnnotationRecord],
        cache_dir: Path,
    ) -> None:
        batch_size = self.settings.annotations_batch_size
        for batch_index, start in enumerate(range(0, len(annotations), batch_size)):
            batch = annotations[start : start + batch_size]
            cache_file = cache_dir / f"batch_{batch_index}.json"

            batch_groundings: list[TextAnnotation]
            if cache_file.exists():
                batch_groundings = self._load_groundings_from_cache(cache_file, batch)
            else:
                batch_groundings = []

            if not batch_groundings:
                batch_groundings = await self._run_grounding_agent(dataset_name, batch)
                cache_file.write_text(
                    json.dumps([entry.model_dump() for entry in batch_groundings], indent=2),
                    encoding="utf-8",
                )

            self._apply_groundings(batch, batch_groundings)

    def _load_groundings_from_cache(
        self,
        cache_file: Path,
        batch: Sequence[AnnotationRecord],
    ) -> list[TextAnnotation]:
        cached_payload = json.loads(cache_file.read_text(encoding="utf-8"))
        expected_inputs = [record.annotation_text or "" for record in batch]
        cached_inputs = [entry.get("input_name", "") for entry in cached_payload]
        if cached_inputs != expected_inputs:
            logger.warning(
                "Cache mismatch detected at %s, regenerating batch.", cache_file
            )
            try:
                cache_file.unlink()
            except FileNotFoundError:
                pass
            return []
        return [TextAnnotation(**entry) for entry in cached_payload]

    async def _run_grounding_agent(
        self, dataset_name: str, batch: Sequence[AnnotationRecord]
    ) -> list[TextAnnotation]:
        logger.info(
            "[%s] Grounding batch of %s annotations",
            dataset_name,
            len(batch),
        )
        expansions_json = json.dumps(
            [
                record.enrichment.model_dump()
                if isinstance(record.enrichment, CellTypeEntry)
                else record.enrichment
                for record in batch
            ],
            indent=2,
        )
        response: TextAnnotationResult = await self.agent.run(expansions_json)
        return response.output.annotations

    def _apply_groundings(
        self,
        batch: Sequence[AnnotationRecord],
        batch_groundings: Sequence[TextAnnotation],
    ) -> None:
        by_input = {}
        for entry in batch_groundings:
            by_input.setdefault(entry.input_name, []).append(entry)

        for record in batch:
            related = by_input.get(record.annotation_text, [])
            chosen = self._select_preferred_grounding(related)
            if chosen:
                record.grounding_cl_id = chosen.cl_id
                record.grounding_cl_label = chosen.cl_label

    def _select_preferred_grounding(
        self, candidates: Sequence[TextAnnotation]
    ) -> TextAnnotation | None:
        for entry in candidates:
            if entry.cl_id and "NO MATCH" not in entry.cl_id:
                return entry
        return candidates[0] if candidates else None

    def _write_reports(self, bundle: PreparedAnnotationBundle) -> None:
        self.layout.output_dir.mkdir(parents=True, exist_ok=True)
        grouped = self._group_by_dataset(bundle.annotations)

        for dataset_name, records in grouped.items():
            if not records:
                continue
            dataset_dir = self.layout.output_dir / dataset_name
            dataset_dir.mkdir(parents=True, exist_ok=True)
            df_all = pd.DataFrame([record.as_dict() for record in records])
            all_annotations_path = dataset_dir / "cell_type_annotations_un_filtered.tsv"
            df_all.to_csv(all_annotations_path, sep="\t", index=False)

            df_filtered = df_all[df_all["grounding_cl_id"].notna()].copy()
            if df_filtered.empty:
                continue
            df_filtered["result"] = df_filtered["cl_id"].eq(
                df_filtered["grounding_cl_id"]
            ).map({True: "TRUE", False: "FALSE"})
            groundings_path = dataset_dir / "groundings.tsv"
            df_filtered.to_csv(groundings_path, sep="\t", index=False)
            logger.info(
                "Saved grounding results for dataset %s to %s",
                dataset_name,
                dataset_dir,
            )

    def _group_by_dataset(
        self, annotations: Sequence[AnnotationRecord]
    ) -> dict[str, list[AnnotationRecord]]:
        grouped: dict[str, list[AnnotationRecord]] = {}
        for record in annotations:
            grouped.setdefault(record.dataset_name, []).append(record)
        return grouped
