"""Dataset loading and preparation utilities for CXG workflows."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

import pandas as pd

from amica.utils.cxg import (
    AnnotationRecord,
    CxgPipelineSettings,
    CxgResourceLayout,
    PreparedAnnotationBundle,
)

logger = logging.getLogger(__name__)


class DatasetLoader:
    """Load CXG TSV files and prepare annotation structures."""

    def __init__(
        self,
        layout: CxgResourceLayout,
        settings: CxgPipelineSettings | None = None,
    ) -> None:
        self.layout = layout
        self.settings = settings or CxgPipelineSettings()

    def load(self) -> PreparedAnnotationBundle:
        """Load annotations from every TSV under the configured input directory."""
        tsv_files = self._discover_input_files()
        if not tsv_files:
            raise FileNotFoundError(
                f"No TSV files found in {self.layout.input_dir}. "
                "Populate the directory or point CXG_RESOURCES_DIR elsewhere."
            )

        bundle = PreparedAnnotationBundle()

        for file_path in tsv_files:
            dataset_name = file_path.stem
            bundle.dataset_names.append(dataset_name)
            logger.info("Loading CXG dataset: %s", dataset_name)
            df = pd.read_csv(file_path, sep="\t")
            self._ingest_dataframe(df, dataset_name, bundle)

        logger.info(
            "Loaded %s annotations from %s dataset(s)",
            len(bundle.annotations),
            len(bundle.dataset_names),
        )

        if self.settings.test_mode:
            self._truncate_for_test_mode(bundle)

        return bundle

    def _discover_input_files(self) -> List[Path]:
        if not self.layout.input_dir.exists():
            logger.warning(
                "Input directory %s does not exist; no datasets discovered.",
                self.layout.input_dir,
            )
            return []

        files = sorted(
            path
            for path in self.layout.input_dir.iterdir()
            if path.suffix.lower() == ".tsv"
        )
        return files

    def _ingest_dataframe(
        self,
        df: pd.DataFrame,
        dataset_name: str,
        bundle: PreparedAnnotationBundle,
    ) -> None:
        for _, row in df.iterrows():
            reference = row.get("reference")
            if pd.isna(reference):
                continue

            paper_doi = str(reference).replace("https://doi.org/", "DOI:")
            record = AnnotationRecord(
                dataset_name=dataset_name,
                annotation_text=str(row.get("author_cell_type", "")).strip(),
                cl_id=_maybe_str(row.get("CL_ID")),
                cl_label=_maybe_str(row.get("CL_label")),
                article_id_doi=paper_doi,
            )

            bundle.annotations.append(record)
            bundle.article_to_annotations.setdefault(paper_doi, []).append(record)

    def _truncate_for_test_mode(self, bundle: PreparedAnnotationBundle) -> None:
        """Limit the number of annotations processed when test mode is enabled."""
        limit = self.settings.test_annotations_count
        bundle.annotations = bundle.annotations[:limit]
        allowed_dois = {record.article_id_doi for record in bundle.annotations}
        bundle.article_to_annotations = {
            doi: records
            for doi, records in bundle.article_to_annotations.items()
            if doi in allowed_dois
        }
        logger.info(
            "Test mode active; truncated annotations to %s entries across %s DOIs",
            len(bundle.annotations),
            len(bundle.article_to_annotations),
        )


def _maybe_str(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value)
