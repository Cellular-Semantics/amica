"""Publication download helpers for CXG workflows."""

from __future__ import annotations

import logging
from typing import Iterable, Set

from amica.utils.cxg import CxgResourceLayout, normalise_identifier
from amica.utils.pubmed_utils import get_doi_text

logger = logging.getLogger(__name__)


class PublicationFetcher:
    """Ensure publication text assets exist on disk for downstream services."""

    def __init__(self, layout: CxgResourceLayout) -> None:
        self.layout = layout

    def ensure_text_assets(self, dois: Iterable[str]) -> Set[str]:
        """Fetch publication text files for the given DOIs if missing."""
        self.layout.publications_dir.mkdir(parents=True, exist_ok=True)
        downloaded: Set[str] = set()

        for doi in dois:
            if not doi:
                continue

            normalised = normalise_identifier(doi)
            file_path = self.layout.publications_dir / f"{normalised}.txt"

            if file_path.exists():
                downloaded.add(doi)
                continue

            text = get_doi_text(doi)
            if not text:
                logger.warning("No full text found for DOI %s", doi)
                continue

            file_path.write_text(text, encoding="utf-8")
            downloaded.add(doi)
            logger.info("Downloaded publication text for %s", doi)

        return downloaded
