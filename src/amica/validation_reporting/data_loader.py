"""Raw data ingestion helpers for validation reporting."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable

import pandas as pd


GROUNDINGS_FILENAME = "groundings.tsv"


def load_grounding_datasets(raw_output_dir: Path) -> dict[str, pd.DataFrame]:
    """Return a mapping of dataset folder -> groundings DataFrame."""
    raw_output_dir = Path(raw_output_dir)
    if not raw_output_dir.exists():
        raise FileNotFoundError(f"raw output directory not found: {raw_output_dir}")

    datasets: dict[str, pd.DataFrame] = {}
    for groundings_file in raw_output_dir.glob(f"**/{GROUNDINGS_FILENAME}"):
        dataset_name = groundings_file.parent.name
        df = pd.read_csv(groundings_file, sep="\t")
        datasets[dataset_name] = df
    if not datasets:
        raise FileNotFoundError(
            f"No {GROUNDINGS_FILENAME} files found under {raw_output_dir}"
        )
    return datasets


@dataclass(slots=True)
class MatchTypeResolver:
    """Caches Pandasaurus match-type lookups for each dataset."""

    match_type_dir: Path
    _cache: Dict[str, dict[tuple[str, str], str]] = field(default_factory=dict)

    def get_map(self, dataset_name: str) -> dict[tuple[str, str], str]:
        """Return the cached match type mapping for a dataset."""
        if dataset_name not in self._cache:
            self._cache[dataset_name] = self._load_dataset_map(dataset_name)
        return self._cache[dataset_name]

    def _load_dataset_map(self, dataset_name: str) -> dict[tuple[str, str], str]:
        base = Path(self.match_type_dir)
        if not base.exists():
            raise FileNotFoundError(
                f"match type directory not found: {self.match_type_dir}"
            )

        for suffix in (".tsv", ".csv"):
            candidate = base / f"{dataset_name}{suffix}"
            if candidate.exists():
                return self._parse_match_types(candidate)
        return {}

    @staticmethod
    def _parse_match_types(path: Path) -> dict[tuple[str, str], str]:
        if path.suffix == ".tsv":
            df = pd.read_csv(path, sep="\t")
        else:
            df = pd.read_csv(path)

        if "author_cell_type" in df.columns:
            df["annotation_text"] = df["author_cell_type"]
        if "CL_ID" in df.columns:
            df["cl_id"] = df["CL_ID"]

        if "match_type" not in df.columns or "cl_id" not in df.columns:
            return {}

        df["annotation_text"] = df["annotation_text"].astype(str).str.strip()
        df["cl_id"] = df["cl_id"].astype(str).str.strip()
        df["match_type"] = (
            df["match_type"].astype(str).str.lower().str.replace(" ", "_")
        )

        return df.set_index(["annotation_text", "cl_id"])["match_type"].to_dict()
