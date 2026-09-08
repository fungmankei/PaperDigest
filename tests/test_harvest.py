from datetime import date

from src import harvest
from src.harvest import _item_to_article, _strip_jats, harvest_journal
from src.journal_registry import Journal


FAKE_CROSSREF = {
    "message": {
        "items": [
            {
                "title": ["Digital platforms in marketing"],
                "author": [{"given": "Jane", "family": "Doe"},
                           {"given": "Rick", "family": "Roe"}],
                "container-title": ["Journal of Marketing"],
                "DOI": "10.1000/xyz",
                "URL": "https://doi.org/10.1000/xyz",
                "published": {"date-parts": [[2026, 8, 28]]},
                "abstract": "<jats:p>We examine <b>digital platforms</b>.</jats:p>",
                "subject": ["Marketing"],
                "ISSN": ["0022-2429"],
            },
            {"title": [], "DOI": "10.1000/empty"},  # skipped (no title)
        ]
    }
}


def test_strip_jats():
    assert _strip_jats("<jats:p>Hello <i>world</i></jats:p>") == "Hello world"
    assert _strip_jats(None) == "No abstract available"


def test_item_to_article():
    art = _item_to_article(FAKE_CROSSREF["message"]["items"][0])
    assert art is not None
    assert art.title == "Digital platforms in marketing"
    assert art.authors == ["Jane Doe", "Rick Roe"]
    assert art.publication_date == "2026-08-28"
    assert "digital platforms" in art.abstract.lower()
    assert _item_to_article({"title": []}) is None


def test_harvest_journal_uses_mock(monkeypatch, sample_config):
    calls = {}

    def fake_request(url, params, mailto, proxies=None, max_retries=3):
        calls["params"] = params
        return FAKE_CROSSREF

    # Avoid touching the real cache/network.
    monkeypatch.setattr(harvest, "_request_json", fake_request)
    monkeypatch.setattr(harvest, "_cache_get", lambda *a, **k: None)
    monkeypatch.setattr(harvest, "_cache_put", lambda *a, **k: None)

    journal = Journal(journal_name="Journal of Marketing", issn=["0022-2429"],
                      journal_weight=25)
    articles = harvest_journal(journal, date(2026, 8, 21), date(2026, 8, 28), sample_config)
    assert len(articles) == 1
    assert articles[0].journal == "Journal of Marketing"
    assert articles[0].journal_weight == 25
    assert "issn:0022-2429" in calls["params"]["filter"]


def test_harvest_journal_api_failure_returns_empty(monkeypatch, sample_config):
    monkeypatch.setattr(harvest, "_request_json", lambda *a, **k: None)
    monkeypatch.setattr(harvest, "_cache_get", lambda *a, **k: None)
    journal = Journal(journal_name="X", issn=["0000-0000"])
    assert harvest_journal(journal, date(2026, 8, 21), date(2026, 8, 28), sample_config) == []
