# Source repo: https://github.com/Cellular-Semantics/agentic-pipeline-testdata/blob/main/src/utils/pubmed_utils.py

import re
from typing import Optional
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

from .doi_fetcher import DOIFetcher

BIOC_URL = "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_xml/{pmid}/ascii"
PUBMED_EUTILS_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmid}&retmode=xml"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={pmid}&retmode=xml"
EUROPEPMC_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={pmid}&resultType=lite&format=json"
CROSSREF_API = "https://api.crossref.org/works/{preprint_doi}"

DOI_PATTERN = r"/(10\.\d{4,9}/[\w\-.]+)"

doi_fetcher = DOIFetcher("ub2@sanger.ac.uk")


def extract_doi_from_url(url: str) -> Optional[str]:
    """Extracts the DOI from a given journal URL.

    Args:
        url (str): The URL of the article.

    Returns:
        str: The extracted DOI if found, otherwise an empty string.

    """
    doi_match = re.search(DOI_PATTERN, url)
    return doi_match.group(1) if doi_match else None


def doi_to_pmid(doi: str) -> Optional[str]:
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": f"{doi}[DOI]",
        "retmode": "xml",
        "tool": "my_doi2pmid_script",
        "email": "ub2@sanger.ac.uk",
        # "api_key": "YOUR_NCBI_API_KEY",  # optional
    }
    headers = {"User-Agent": "my_doi2pmid_script (mailto:ub2@sanger.ac.uk)"}
    resp = requests.get(url, params=params, headers=headers)
    resp.raise_for_status()
    root = ElementTree.fromstring(resp.text)
    id_el = root.find(".//IdList/Id")
    return id_el.text if id_el is not None else None


def get_doi_text(doi: str) -> str:
    """
    Fetch the full text of an article given any DOI (preprint or journal).

    1. Try DOI → PMID via PubMed (doi_to_pmid)
    2. If that fails, ask Crossref for `is-preprint-of` relations
    3. If still no PMID, fall back to Unpaywall’s `get_full_text`
    4. If all else fails, return empty string

    Args:
        doi: The DOI of the (possibly preprint) article.

    Returns:
        Full text string, or "" if unavailable.
    """
    # 1) PubMed lookup
    pmid = doi_to_pmid(doi)
    if pmid:
        return get_pmid_text(pmid)

    # 2) Crossref: preprint → published DOI → PMID
    published = _crossref_published_doi(doi)
    if published:
        pmid = doi_to_pmid(published)
        if pmid:
            return get_pmid_text(pmid)

    # 3) Unpaywall direct full-text
    info = doi_fetcher.get_full_text(doi)
    if info:
        return info

    # nothing found
    return ""


def _crossref_published_doi(preprint_doi: str) -> Optional[str]:
    """Return the journal-article DOI linked to this preprint via Crossref."""
    try:
        resp = requests.get(CROSSREF_API.format(preprint_doi=preprint_doi), timeout=5)
        resp.raise_for_status()
        relations = resp.json()["message"].get("relation", {})
        pre2pub = relations.get("is-preprint-of", [])
        return pre2pub[0]["id"] if pre2pub else None
    except (requests.RequestException, KeyError, IndexError):
        return None


def get_pmid_from_pmcid(pmcid):
    """Fetch the PMID from a PMC ID using the Entrez E-utilities `esummary`.

    Example:
        >>> pmcid = "PMC5048378"
        >>> pmid = get_pmid_from_pmcid(pmcid)
        >>> print(pmid)
        27629041

    Args:
        pmcid:

    Returns:

    """
    if ":" in pmcid:
        pmcid = pmcid.split(":")[1]
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    params = {
        "db": "pmc",
        "id": pmcid.replace("PMC", ""),
        "retmode": "json",
    }  # Remove "PMC" prefix if included

    response = requests.get(url, params=params)
    data = response.json()

    # Extract PMID
    try:
        uid = data["result"]["uids"][0]  # Extract the UID
        article_ids = data["result"][uid]["articleids"]  # Get article IDs
        for item in article_ids:
            if item["idtype"] == "pmid":
                return item["value"]
    except KeyError:
        return "PMID not found"


def get_pmcid_text(pmcid: str) -> str:
    """Fetch full text from PubMed Central Open Access BioC XML.

    Example:
        >>> pmcid = "PMC5048378"
        >>> full_text = get_pmcid_text(pmcid)
        >>> assert "integrated stress response (ISR)" in full_text

    Args:
        pmcid:
        xml:

    Returns:

    """
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {
        "db": "pmc",
        "id": pmcid,
        "retmode": "xml",
    }
    try:
        resp = requests.get(base, params=params, timeout=60)
        print(f"Response code: {resp.status_code}")
        print(f"Effective URL: {resp.url}")
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "xml")
        text = soup.get_text(separator=" ")
        if text:
            return text
    except Exception as e:
        print(e)
    pmid = get_pmid_from_pmcid(pmcid)
    return get_pmid_text(pmid)


def get_pmid_text(pmid: str) -> str:
    """Fetch full text from PubMed Central Open Access BioC XML.
    If full text is not available, fallback to fetching the abstract from PubMed.

    Example:
        >>> pmid = "11"
        >>> full_text = get_pmid_text(pmid)
        >>> print(full_text)
        Identification of adenylate cyclase-coupled beta-adrenergic receptors with radiolabeled beta-adrenergic antagonists.
        <BLANKLINE>
        No abstract available

    Args:
        pmid: PubMed ID of the article.

    Returns:
        The full text of the article if available, otherwise the abstract.

    """
    if ":" in pmid:
        pmid = pmid.split(":")[1]
    text = get_full_text_from_bioc(pmid)
    if not text:
        resp = requests.get(EUROPEPMC_URL.format(pmid=pmid))
        resp.raise_for_status()
        results = resp.json()["resultList"]["result"]
        if not results:
            text = None
        else:
            full_ids = results[0].get("fullTextIdList", {}).get("fullTextId", [])
            if full_ids:
                pmcid = full_ids[0]
                text = get_pmcid_text(pmcid)
    if not text:
        doi = pmid_to_doi(pmid)
        if doi:
            text = doi_fetcher.get_full_text(doi)
    if not text:
        text = get_abstract_from_pubmed(pmid)
    return text


def pmid_to_doi(pmid: str) -> Optional[str]:
    if ":" in pmid:
        pmid = pmid.split(":")[1]
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmid}&retmode=json"
    response = requests.get(url)
    data = response.json()

    try:
        article_info = data["result"][str(pmid)]
        for aid in article_info["articleids"]:
            if aid["idtype"] == "doi":
                return aid["value"]
        elocationid = article_info.get("elocationid", "")
        if elocationid.startswith("10."):  # DOI starts with "10."
            return elocationid
        else:
            return None
    except KeyError:
        return None


def get_full_text_from_bioc(pmid: str, timeout: float = 10.0) -> str:
    """Fetch full text from PubMed Central Open Access BioC XML.

    Example:
        >>> pmid = "17299597"
        >>> full_text = get_full_text_from_bioc(pmid)
        >>> assert "Evolution of biological complexity." in full_text

    Args:
        pmid: PubMed ID of the article.
        timeout: Timeout in seconds

    Returns:
        The full text of the article if available, otherwise an empty string.

    """
    try:
        response = requests.get(BIOC_URL.format(pmid=pmid), timeout=timeout)
        response.raise_for_status()
    except (requests.exceptions.Timeout, requests.exceptions.RequestException):
        # Log a warning here if you have logging configured
        return ""  # Gracefully return empty string on any error

    soup = BeautifulSoup(response.text, "xml")

    # Extract ONLY text from <text> tags within <passage>
    text_sections = [text_tag.get_text() for text_tag in soup.find_all("text")]

    full_text = "\n".join(text_sections).strip()
    return full_text


def get_abstract_from_pubmed(pmid: str) -> str:
    """Fetch the title and abstract of an article from PubMed using Entrez E-utilities `efetch`.

    Example:
        >>> pmid = "31653696"
        >>> abstract = get_abstract_from_pubmed(pmid)
        >>> assert "The apparent deglycase activity of DJ-1" in abstract

    Args:
        pmid: PubMed ID of the article.

    Returns:
        The title and abstract text if available, otherwise an empty string.

    """
    response = requests.get(EFETCH_URL.format(pmid=pmid))

    if response.status_code != 200:
        return ""

    soup = BeautifulSoup(response.text, "xml")

    # Extract title
    title_tag = soup.find("ArticleTitle")
    title = title_tag.get_text().strip() if title_tag else "No title available"

    # Extract abstract (may contain multiple sections)
    abstract_tags = soup.find_all("AbstractText")
    abstract = (
        "\n".join(tag.get_text().strip() for tag in abstract_tags)
        if abstract_tags
        else "No abstract available"
    )

    return f"{title}\n\n{abstract}"

