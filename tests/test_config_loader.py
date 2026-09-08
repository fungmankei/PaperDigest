import pytest
import yaml

from src.config_loader import ConfigError, load_areas, load_config


def _write(tmp_path, data):
    p = tmp_path / "user_config.yaml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    return p


BASE = {
    "areas": ["Marketing"],
    "keywords": ["digital platforms"],
    "journal_inclusion": {"abs_min_level": 3, "abdc_grades": ["A*"], "sjr_quartile": "Q1"},
    "relevance_threshold": 80,
    "journal_weight_factor": 0.3,
    "email": {"address": "a@b.c", "smtp_server": "smtp.b.c", "smtp_port": 587},
    "ai_settings": {"use_ai_agents": False},
}


def test_load_valid_config(tmp_path):
    cfg = load_config(_write(tmp_path, BASE))
    assert cfg.areas == ["Marketing"]
    assert cfg.journal_inclusion.abs_min_level == 3.0
    assert cfg.email.from_address == "a@b.c"      # defaulted from address
    assert cfg.harvest.crossref_mailto == "a@b.c" # defaulted from email


def test_env_var_overrides_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("DIGEST_SMTP_PASSWORD", "from-env")
    cfg = load_config(_write(tmp_path, BASE))
    assert cfg.email.smtp_password == "from-env"


def test_missing_keywords_raises(tmp_path):
    data = dict(BASE)
    data["keywords"] = []
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, data))


def test_bad_weight_factor_raises(tmp_path):
    data = dict(BASE)
    data["journal_weight_factor"] = 2.0
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, data))


def test_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.yaml")


def test_load_areas():
    areas = load_areas()
    assert "Marketing" in areas
    assert "Information Systems" in areas
