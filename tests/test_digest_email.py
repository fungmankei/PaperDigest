import smtplib

import pytest

from src import email_sender
from src.digest_builder import build_digest, build_heartbeat
from src.email_sender import EmailError, send_digest
from src.harvest import Article


def _articles(n):
    return [Article(title=f"Article {i}", authors=[f"Author {i}"],
                    journal="Journal of Marketing", abstract=f"Abstract {i}",
                    final_score=90 - i, summary=f"Summary {i}",
                    relevance_explanation="Relevant.") for i in range(n)]


def test_build_digest_top_and_rest():
    digest = build_digest(_articles(25))
    assert digest.top_count == 20
    assert digest.total == 25
    assert "Article 0" in digest.html and "Article 0" in digest.text
    # 21st article (index 20) should appear in the "rest" section only (brief).
    assert "Summary 24" not in digest.text     # rest items have no summary
    assert "Article 24" in digest.text


def test_build_digest_escapes_html():
    arts = _articles(1)
    arts[0].title = "A <script> & platforms"
    digest = build_digest(arts)
    assert "<script>" not in digest.html
    assert "&lt;script&gt;" in digest.html


def test_heartbeat():
    hb = build_heartbeat()
    assert hb.total == 0
    assert "no new" in hb.subject.lower()


def test_send_digest_dry_run(sample_config, capsys):
    digest = build_digest(_articles(3))
    assert send_digest(sample_config.email, digest, dry_run=True) is True
    out = capsys.readouterr().out
    assert "SUBJECT:" in out


def test_send_digest_success(monkeypatch, sample_config):
    sent = {}

    class FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self, context=None): sent["tls"] = True
        def login(self, u, p): sent["login"] = u
        def send_message(self, msg): sent["msg"] = msg

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    sample_config.email.smtp_password = "secret"
    digest = build_digest(_articles(2))
    assert send_digest(sample_config.email, digest) is True
    assert "msg" in sent and sent["tls"] is True


def test_send_digest_retries_then_fails(monkeypatch, sample_config):
    attempts = {"n": 0}

    def boom(cfg, msg):
        attempts["n"] += 1
        raise smtplib.SMTPException("nope")

    monkeypatch.setattr(email_sender, "_send_once", boom)
    digest = build_digest(_articles(1))
    with pytest.raises(EmailError):
        send_digest(sample_config.email, digest)
    assert attempts["n"] == 2  # one send + one retry
