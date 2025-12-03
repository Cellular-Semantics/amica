from __future__ import annotations

import types

import pytest

from amica.utils.doi_fetcher import DOIFetcher, FullTextInfo


class DummyResponse:
    def __init__(self, *, status_code: int = 200, json_data=None, text="", content=b""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text
        self.content = content

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("boom")

    def json(self):
        return self._json_data


@pytest.mark.unit
def test_clean_text_normalises_whitespace() -> None:
    fetcher = DOIFetcher()
    raw = "Line 1\nLine 2\t\u200b"
    assert fetcher.clean_text(raw) == "Line 1 Line 2"


@pytest.mark.unit
def test_get_metadata_returns_message(monkeypatch) -> None:
    def fake_get(url, headers=None, timeout=30):
        assert "api.crossref.org" in url
        return DummyResponse(json_data={"message": {"title": ["demo"]}})

    monkeypatch.setattr("amica.utils.doi_fetcher.requests.get", fake_get)
    fetcher = DOIFetcher()
    message = fetcher.get_metadata("10.1000/demo")
    assert message == {"title": ["demo"]}


@pytest.mark.unit
def test_get_unpaywall_info_returns_payload(monkeypatch) -> None:
    def fake_get(url, timeout=30):
        assert "api.unpaywall.org" in url
        return DummyResponse(json_data={"doi": "10.1000/demo"})

    monkeypatch.setattr("amica.utils.doi_fetcher.requests.get", fake_get)
    fetcher = DOIFetcher(email="tester@example.com")
    payload = fetcher.get_unpaywall_info("10.1000/demo")
    assert payload == {"doi": "10.1000/demo"}


@pytest.mark.unit
def test_get_full_text_info_prefers_unpaywall(monkeypatch) -> None:
    fetcher = DOIFetcher()
    monkeypatch.setattr(
        fetcher,
        "get_metadata",
        lambda doi: {"title": ["demo"]},
    )
    monkeypatch.setattr(
        fetcher,
        "get_unpaywall_info",
        lambda doi: {
            "is_oa": True,
            "best_oa_location": {"url_for_pdf": "https://example.com/demo.pdf"},
        },
    )
    info = fetcher.get_full_text_info("10.1000/demo")
    assert isinstance(info, FullTextInfo)
    assert info.pdf_url == "https://example.com/demo.pdf"
    assert info.source == "unpaywall"
    assert info.metadata["title"] == ["demo"]


@pytest.mark.unit
def test_get_full_text_info_falls_back_to_prefix(monkeypatch) -> None:
    html = '<html><body><embed id="pdf" src="//downloads/demo.pdf#view=fit"></body></html>'

    def fake_get(url, *args, **kwargs):
        return DummyResponse(status_code=200, text=html)

    fetcher = DOIFetcher(url_prefixes=["https://example.com"])
    monkeypatch.setattr(fetcher, "get_metadata", lambda doi: {})
    monkeypatch.setattr(fetcher, "get_unpaywall_info", lambda doi: {})
    monkeypatch.setattr("amica.utils.doi_fetcher.requests.get", fake_get)
    info = fetcher.get_full_text_info("10.1000/demo")
    assert info.pdf_url == "https://downloads/demo.pdf"
    assert info.source == "https://example.com/10.1000/demo"


@pytest.mark.unit
def test_text_from_pdf_url_invokes_markitdown(monkeypatch) -> None:
    fake_session = types.SimpleNamespace()

    def fake_get(url, headers=None, allow_redirects=True):
        return DummyResponse(status_code=200, content=b"PDFDATA")

    fake_session.get = fake_get
    monkeypatch.setattr(
        "amica.utils.doi_fetcher.requests.Session",
        lambda: fake_session,
    )

    class FakeMarkdown:
        def convert(self, path):
            return types.SimpleNamespace(text_content="pdf text")

    monkeypatch.setattr("amica.utils.doi_fetcher.MarkItDown", lambda: FakeMarkdown())

    fetcher = DOIFetcher()
    text = fetcher.text_from_pdf_url("https://example.com/demo.pdf")
    assert text == "pdf text"


@pytest.mark.unit
def test_text_from_pdf_url_handles_non_200(monkeypatch) -> None:
    fake_session = types.SimpleNamespace()

    def fake_get(url, headers=None, allow_redirects=True):
        return DummyResponse(status_code=404)

    fake_session.get = fake_get
    monkeypatch.setattr("amica.utils.doi_fetcher.requests.Session", lambda: fake_session)
    fetcher = DOIFetcher()
    assert fetcher.text_from_pdf_url("https://example.com/bad.pdf") is None


@pytest.mark.unit
def test_get_full_text_prefers_cleaned_text(monkeypatch) -> None:
    fetcher = DOIFetcher()

    def fake_full_text_info(doi: str):
        return FullTextInfo(text="  demo  ", metadata={"abstract": "ignored"})

    monkeypatch.setattr(fetcher, "get_full_text_info", fake_full_text_info)
    assert fetcher.get_full_text("10.1000/demo") == "demo"


@pytest.mark.unit
def test_get_full_text_returns_pdf_bytes(monkeypatch) -> None:
    fetcher = DOIFetcher()
    monkeypatch.setattr(fetcher, "get_full_text_info", lambda doi: None)

    def fake_get(url, headers=None):
        return DummyResponse(status_code=200, content=b"PDF")

    monkeypatch.setattr("amica.utils.doi_fetcher.requests.get", fake_get)
    assert fetcher.get_full_text("10.1000/demo") == b"PDF"


@pytest.mark.unit
def test_get_full_text_falls_back_to_abstract(monkeypatch) -> None:
    fetcher = DOIFetcher()

    def fake_full_text_info(doi: str):
        return FullTextInfo(text=None, pdf_url=None, metadata={"abstract": "Summary"})

    monkeypatch.setattr(fetcher, "get_full_text_info", fake_full_text_info)
    assert fetcher.get_full_text("10.1000/demo") == "Summary\n\nFULL TEXT NOT AVAILABLE"
