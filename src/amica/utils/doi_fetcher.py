# Source repo: https://github.com/Cellular-Semantics/agentic-pipeline-testdata/blob/main/src/utils/doi_fetcher.py

import logging
import os
import re
from contextlib import suppress
from dataclasses import dataclass, field
from tempfile import NamedTemporaryFile
from typing import Any

import requests
from bs4 import BeautifulSoup
from markitdown import MarkItDown

# Configure module logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@dataclass
class FullTextInfo:
    """Data model for full text information."""

    text: str | None = None
    pdf_url: str | None = None
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class DOIFetcher:
    """Fetch metadata and full text for a DOI using various APIs."""

    def __init__(
        self,
        email: str | None = None,
        url_prefixes: list[str] | None = None,
        cache_name: str = "pdf_cache",
        expire_after: int = 86400,
    ):
        """Initialize the DOI fetcher with a contact email (required by some APIs).

        Args:
            email (str): Contact email for API access
            url_prefixes (List[str]): List of URL prefixes to check for full text

        """
        # contact email
        self.email = email or os.getenv("EMAIL") or "test@example.com"
        self.headers = {
            "User-Agent": f"DOIFetcher/1.0 (mailto:{self.email})",
            "Accept": "application/json",
        }
        # fallback URL prefixes
        self.url_prefixes = url_prefixes or os.getenv("DOI_FULL_TEXT_URLS", "").split(",")

    def clean_text(self, text: str) -> str:
        """Clean extracted text by removing extra whitespace and normalized characters.

        Args:
            text:

        Returns:
            str: The cleaned text

        """
        text = re.sub(r"\s+", " ", text)
        text = "".join(ch for ch in text if ch.isprintable())
        return text.strip()

    def get_metadata(self, doi: str, strict: bool = False) -> dict[str, Any] | None:
        """Fetch metadata for a DOI using the Crossref API.

        Args:
            doi (str): The DOI to look up
            strict (bool): Raise exceptions if API call fails

        Returns:
            Optional[Dict[str, Any]]: Metadata dictionary if successful, None otherwise

        """
        base_url = "https://api.crossref.org/works/"
        try:
            resp = requests.get(f"{base_url}{doi}", headers=self.headers, timeout=30)
            resp.raise_for_status()
            return resp.json().get("message")
        except Exception as err:  # noqa: BLE001
            if strict:
                raise
            logger.warning("Error fetching metadata: %s", err)
            return None

    def get_unpaywall_info(self, doi: str, strict: bool = False) -> dict[str, Any] | None:
        """Check Unpaywall for open access versions.

        Example:
            >>> fetcher = DOIFetcher()
            >>> doi = "10.1038/nature12373"
            >>> unpaywall_data = fetcher.get_unpaywall_info(doi)
            >>> assert unpaywall_data["doi"] == doi
            >>> unpaywall_data["best_oa_location"]["url_for_pdf"]
            'https://europepmc.org/articles/pmc4221854?pdf=render'

        Args:
            doi (str): The DOI to look up
            strict (bool): Raise exceptions if API call fails

        Returns:
            Optional[Dict[str, Any]]: Unpaywall data if successful, None otherwise

        """
        base_url = f"https://api.unpaywall.org/v2/{doi}?email={self.email}"
        try:
            resp = requests.get(base_url, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as err:  # noqa: BLE001
            if strict:
                raise
            logger.warning("Error fetching Unpaywall data: %s", err)
            return None

    def get_full_text_info(self, doi: str) -> FullTextInfo | None:
        """Attempt to get the full text of a paper using various methods.

            >>> fetcher = DOIFetcher()
            >>> doi = "10.1128/msystems.00045-18"
            >>> info = fetcher.get_full_text_info(doi)
            >>> metadata = info.metadata
            >>> metadata["type"]
            'journal-article'
            >>> metadata["title"][0][0:20]
            'Exploration of the B'
            >>> assert info.pdf_url is not None
            >>> info.pdf_url
            'https://europepmc.org/articles/pmc6172771?pdf=render'

        Args:
            doi (str): The DOI to fetch

        Returns:
            FullTextInfo: Full text information

        """
        metadata = self.get_metadata(doi) or {}
        # try Unpaywall
        up = self.get_unpaywall_info(doi) or {}
        if up.get("is_oa") and up.get("best_oa_location"):
            best = up["best_oa_location"]
            pdf_url = best.get("url_for_pdf")
            if pdf_url:
                return FullTextInfo(
                    text=None, pdf_url=pdf_url, source="unpaywall", metadata=metadata
                )
        # fallback to prefixes
        for prefix in self.url_prefixes:
            url = f"{prefix.rstrip('/')}/{doi}"
            try:
                resp = requests.get(url, timeout=30)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    embed = soup.find("embed", id="pdf")
                    if embed and embed.get("src"):
                        src = embed["src"].split("#")[0]
                        pdf_url = src if src.startswith("http") else f"https:{src}"
                        return FullTextInfo(
                            text=None, pdf_url=pdf_url, source=url, metadata=metadata
                        )
            except Exception:  # noqa: BLE001
                continue
        return None

    def text_from_pdf_url(self, pdf_url: str, raise_for_status: bool = False) -> str | None:
        """Extract text from a PDF URL.

        Example:
            >>> fetcher = DOIFetcher()
            >>> pdf_url = "https://ceur-ws.org/Vol-1747/IT201_ICBO2016.pdf"
            >>> text = fetcher.text_from_pdf_url(pdf_url)
            >>> assert "biosphere" in text

        Args:
            pdf_url:
            raise_for_status:

        Returns:

        """
        try:
            # Use a session so that cookies (if any) can be handled automatically
            session = requests.Session()
            headers = {
                # A more “real” User-Agent
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/114.0.0.0 Safari/537.36"
                ),
                # Tell the server which content types you accept
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;"
                    "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
                ),
                "Accept-Language": "en-GB,en;q=0.9",
                # Make sure to point back at the article landing page
                "Referer": pdf_url.replace("/article-pdf/", "/article/"),
                # Some servers also look at “Connection”
                "Connection": "keep-alive",
            }

            resp = session.get(pdf_url, headers=headers, allow_redirects=True)
            if raise_for_status:
                resp.raise_for_status()
            if resp.status_code != 200:
                return None

            # write out to a temporary file
            with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(resp.content)
                path = tmp.name

            # convert PDF → text via MarkItDown
            md = MarkItDown()
            out = md.convert(path).text_content

            # clean up
            with suppress(OSError):
                os.remove(path)

            return out

        except Exception:  # noqa: BLE001
            # you might want to log this exception here if needed
            return None

    def get_full_text(self, doi: str, fallback_to_abstract: bool = True) -> str | bytes | None:
        """
        Retrieve full text (HTML or PDF binary) of a paper by DOI.

        Returns:
            - Cleaned full text string if available
            - Raw PDF content (bytes) if full text not available but PDF is fetched
            - Abstract string (with fallback note) if fallback is enabled and full text
              is unavailable
            - None if nothing could be retrieved
        """
        info = self.get_full_text_info(doi)
        if not info:
            pdf_url = f"https://www.annualreviews.org/doi/pdf/{doi}"
            headers = {
                "User-Agent": "Mozilla/5.0",
            }
            r = requests.get(pdf_url, headers=headers)
            if r.status_code == 200:
                return r.content
            else:
                return None
        text = info.text
        if text:
            return self.clean_text(text)
        if info.pdf_url:
            text = self.text_from_pdf_url(info.pdf_url)
            if text:
                return self.clean_text(text)
        message = "FULL TEXT NOT AVAILABLE"
        if fallback_to_abstract:
            metadata = info.metadata or {}
            abstract = metadata.get("abstract")
            if abstract:
                return self.clean_text(abstract) + f"\n\n{message}"
        return message
