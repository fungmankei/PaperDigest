"""End-to-end pipeline test using mocked CrossRef + SMTP and sample data."""
from datetime import date

from src import harvest
from src.main import run_pipeline


FAKE_ITEMS = [
    {
        "title": ["Digital platforms and causal inference"],
        "author": [{"given": "A", "family": "One"}],
        "container-title": ["Journal of Marketing"],
        "DOI": "10.1/a",
        "URL": "http://x/a",
        "published": {"date-parts": [[2026, 8, 28]]},
        "abstract": "<jats:p>Digital platforms and causal inference in markets.</jats:p>",
        "subject": ["Marketing"],
        "ISSN": ["0022-2429"],
    },
]


def test_full_pipeline_dry_run(monkeypatch, sample_config, capsys):
    # Every CrossRef call returns the same one relevant article.
    monkeypatch.setattr(harvest, "_request_json",
                        lambda *a, **k: {"message": {"items": FAKE_ITEMS}})
    monkeypatch.setattr(harvest, "_cache_get", lambda *a, **k: None)
    monkeypatch.setattr(harvest, "_cache_put", lambda *a, **k: None)

    # Lower the threshold so the article passes regardless of exact scoring.
    sample_config.relevance_threshold = 20
    sample_config.harvest.max_workers = 2

    n = run_pipeline(sample_config, to_date=date(2026, 8, 28),
                     dry_run=True, send_email=True)
    assert n >= 1
    out = capsys.readouterr().out
    assert "Digital platforms" in out
    assert "SUBJECT:" in out


def test_pipeline_no_articles_sends_heartbeat(monkeypatch, sample_config, capsys):
    monkeypatch.setattr(harvest, "_request_json",
                        lambda *a, **k: {"message": {"items": []}})
    monkeypatch.setattr(harvest, "_cache_get", lambda *a, **k: None)
    monkeypatch.setattr(harvest, "_cache_put", lambda *a, **k: None)

    n = run_pipeline(sample_config, to_date=date(2026, 8, 28),
                     dry_run=True, send_email=True)
    assert n == 0
    out = capsys.readouterr().out
    assert "no new articles" in out.lower()
