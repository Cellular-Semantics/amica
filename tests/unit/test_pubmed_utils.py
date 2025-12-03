from __future__ import annotations

import types

import pytest
import requests

import amica.utils.pubmed_utils as pubmed_utils


class DummyResponse:
    def __init__(self, text="", json_data=None, status_code=200, url="https://example.com"):
        self.text = text
        self._json_data = json_data or {}
        self.status_code = status_code
        self.url = url

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("boom")

    def json(self):
        return self._json_data


@pytest.mark.unit
def test_extract_doi_from_url() -> None:
    url = "https://journal.org/article/10.1000/demo"
    assert pubmed_utils.extract_doi_from_url(url) == "10.1000/demo"
    assert pubmed_utils.extract_doi_from_url("https://journal.org/article") is None


@pytest.mark.unit
def test_doi_to_pmid_parses_xml(monkeypatch) -> None:
    xml = "<eSearchResult><IdList><Id>1234</Id></IdList></eSearchResult>"

    def fake_get(url, params=None, headers=None):
        return DummyResponse(text=xml)

    monkeypatch.setattr("amica.utils.pubmed_utils.requests.get", fake_get)
    assert pubmed_utils.doi_to_pmid("10.1000/demo") == "1234"


@pytest.mark.unit
def test_crossref_published_doi(monkeypatch) -> None:
    def fake_get(url, timeout=5):
        return DummyResponse(
            json_data={
                "message": {
                    "relation": {
                        "is-preprint-of": [{"id": "10.1000/journal"}],
                    }
                }
            }
        )

    monkeypatch.setattr("amica.utils.pubmed_utils.requests.get", fake_get)
    assert pubmed_utils._crossref_published_doi("10.1000/preprint") == "10.1000/journal"


@pytest.mark.unit
def test_get_doi_text_prefers_pmid(monkeypatch) -> None:
    monkeypatch.setattr("amica.utils.pubmed_utils.doi_to_pmid", lambda doi: "12345")
    monkeypatch.setattr("amica.utils.pubmed_utils.get_pmid_text", lambda pmid: "full text")
    text = pubmed_utils.get_doi_text("10.1000/demo")
    assert text == "full text"


@pytest.mark.unit
def test_get_doi_text_falls_back_to_doi_fetcher(monkeypatch) -> None:
    monkeypatch.setattr("amica.utils.pubmed_utils.doi_to_pmid", lambda doi: None)
    monkeypatch.setattr("amica.utils.pubmed_utils._crossref_published_doi", lambda doi: None)
    fake_fetcher = types.SimpleNamespace(get_full_text=lambda doi: "fallback text")
    monkeypatch.setattr("amica.utils.pubmed_utils.doi_fetcher", fake_fetcher)
    assert pubmed_utils.get_doi_text("10.1000/demo") == "fallback text"


@pytest.mark.unit
def test_get_pmid_text_prefers_bioc(monkeypatch) -> None:
    monkeypatch.setattr("amica.utils.pubmed_utils.get_full_text_from_bioc", lambda pmid: "bioctext")
    assert pubmed_utils.get_pmid_text("PMID:123") == "bioctext"


@pytest.mark.unit
def test_get_pmid_text_falls_back_to_abstract(monkeypatch) -> None:
    monkeypatch.setattr("amica.utils.pubmed_utils.get_full_text_from_bioc", lambda pmid: "")

    def fake_get(url):
        return DummyResponse(
            json_data={"resultList": {"result": [{"fullTextIdList": {"fullTextId": ["PMC123"]}}]}},
            status_code=200,
        )

    def fake_get_pmcid_text(pmcid):
        return ""

    monkeypatch.setattr("amica.utils.pubmed_utils.requests.get", fake_get)
    monkeypatch.setattr("amica.utils.pubmed_utils.get_pmcid_text", fake_get_pmcid_text)
    monkeypatch.setattr(
        "amica.utils.pubmed_utils.pmid_to_doi",
        lambda pmid: "10.1000/demo",
    )
    fake_fetcher = types.SimpleNamespace(get_full_text=lambda doi: "")
    monkeypatch.setattr("amica.utils.pubmed_utils.doi_fetcher", fake_fetcher)
    monkeypatch.setattr(
        "amica.utils.pubmed_utils.get_abstract_from_pubmed",
        lambda pmid: "Abstract text",
    )

    assert pubmed_utils.get_pmid_text("123") == "Abstract text"


@pytest.mark.unit
def test_pmid_to_doi_extracts_value(monkeypatch) -> None:
    payload = {
        "result": {
            "12345": {
                "articleids": [{"idtype": "doi", "value": "10.1000/demo"}],
            }
        }
    }

    def fake_get(url):
        return DummyResponse(json_data=payload)

    monkeypatch.setattr("amica.utils.pubmed_utils.requests.get", fake_get)
    assert pubmed_utils.pmid_to_doi("12345") == "10.1000/demo"


@pytest.mark.unit
def test_get_full_text_from_bioc_parses_text(monkeypatch) -> None:
    xml = (
        "<root><passage><text>Line A</text></passage><passage><text>Line B</text></passage></root>"
    )

    def fake_get(url, timeout=10.0):
        return DummyResponse(text=xml)

    monkeypatch.setattr("amica.utils.pubmed_utils.requests.get", fake_get)
    text = pubmed_utils.get_full_text_from_bioc("12345")
    assert "Line A" in text and "Line B" in text


@pytest.mark.unit
def test_get_full_text_from_bioc_handles_error(monkeypatch) -> None:
    def fake_get(url, timeout=10.0):
        raise requests.exceptions.Timeout()

    monkeypatch.setattr("amica.utils.pubmed_utils.requests.get", fake_get)
    assert pubmed_utils.get_full_text_from_bioc("12345") == ""


@pytest.mark.unit
def test_get_abstract_from_pubmed_parses_title_and_abstract(monkeypatch) -> None:
    xml = """
    <root>
        <ArticleTitle>Sample Title</ArticleTitle>
        <AbstractText>Paragraph one.</AbstractText>
        <AbstractText>Paragraph two.</AbstractText>
    </root>
    """

    def fake_get(url):
        return DummyResponse(status_code=200, text=xml)

    monkeypatch.setattr("amica.utils.pubmed_utils.requests.get", fake_get)
    text = pubmed_utils.get_abstract_from_pubmed("12345")
    assert "Sample Title" in text
    assert "Paragraph two." in text


@pytest.mark.unit
def test_get_pmid_from_pmcid_parses_json(monkeypatch) -> None:
    payload = {
        "result": {
            "uids": ["1"],
            "1": {"articleids": [{"idtype": "pmid", "value": "12345"}]},
        }
    }

    def fake_get(url, params=None):
        return DummyResponse(json_data=payload)

    monkeypatch.setattr("amica.utils.pubmed_utils.requests.get", fake_get)
    assert pubmed_utils.get_pmid_from_pmcid("PMC1") == "12345"


@pytest.mark.unit
def test_get_pmcid_text_prefers_direct_fetch(monkeypatch) -> None:
    xml = "<root><text>PMCID text</text></root>"

    def fake_get(url, params=None, timeout=60):
        if "efetch.fcgi" in url:
            return DummyResponse(text=xml)
        raise AssertionError("unexpected url")

    monkeypatch.setattr("amica.utils.pubmed_utils.requests.get", fake_get)
    text = pubmed_utils.get_pmcid_text("PMC123")
    assert "PMCID text" in text
