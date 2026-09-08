"""Load, validate, and normalise user configuration.

Configuration lives in ``config/user_config.yaml``. Secrets may be supplied via
environment variables which take precedence over file values:

    DIGEST_SMTP_PASSWORD  -> email.smtp_password
    DIGEST_LLM_API_KEY    -> ai_settings.llm_api_key
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

# Repository layout: <root>/src/config_loader.py  ->  <root>
ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "data"
LOGS_DIR = ROOT_DIR / "logs"

DEFAULT_CONFIG_PATH = CONFIG_DIR / "user_config.yaml"
EXAMPLE_CONFIG_PATH = CONFIG_DIR / "user_config.example.yaml"
AREAS_PATH = CONFIG_DIR / "areas.yaml"


class ConfigError(Exception):
    """Raised when the configuration is missing or invalid."""


@dataclass
class EmailConfig:
    address: str
    smtp_server: str
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    from_address: Optional[str] = None
    use_tls: bool = True
    send_heartbeat: bool = True

    def __post_init__(self) -> None:
        self.from_address = self.from_address or self.address
        self.smtp_username = self.smtp_username or self.address


@dataclass
class JournalInclusion:
    abs_min_level: Optional[float] = None
    abdc_grades: list[str] = field(default_factory=list)
    sjr_quartile: Optional[str] = None
    include_ft50: bool = True
    include_utd24: bool = True


@dataclass
class AISettings:
    use_ai_agents: bool = False
    embedding_model: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    ai_weight: float = 0.5


@dataclass
class AccessSettings:
    proxy_url: Optional[str] = None
    cookies_file: Optional[str] = None


@dataclass
class HarvestSettings:
    crossref_mailto: Optional[str] = None
    max_workers: int = 8
    cache_ttl_hours: int = 24
    max_articles_per_journal: int = 50
    enable_scraping_fallback: bool = True
    registry_file: Optional[str] = None   # override data/journals.csv (e.g. the elite subset)
    elite_only: bool = False              # monitor only elite journals (FT50/UTD24/ABS 4*,4/ABDC A*)


@dataclass
class Config:
    areas: list[str]
    keywords: list[str]
    journal_inclusion: JournalInclusion
    relevance_threshold: float
    journal_weight_factor: float
    email: EmailConfig
    ai_settings: AISettings
    access: AccessSettings
    harvest: HarvestSettings
    harvest_window_days: int = 7
    raw: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# ABS/AJG level parsing helpers (shared with the journal registry).
# --------------------------------------------------------------------------- #
def parse_abs_level(value: Any) -> Optional[float]:
    """Convert an ABS/AJG level to a comparable float. ``4*`` -> 4.5."""
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in ("", "n/a", "na", "none", "-"):
        return None
    text = text.replace("*", ".5") if text.endswith("*") else text
    try:
        return float(text)
    except ValueError:
        return None


def load_areas(path: Path = AREAS_PATH) -> list[str]:
    """Return the list of selectable research areas (the CLI 'drop down')."""
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list(data.get("areas", []))


def _require(d: dict, key: str, ctx: str) -> Any:
    if key not in d:
        raise ConfigError(f"Missing required config key '{key}' in {ctx}.")
    return d[key]


def load_config(path: Path | str = DEFAULT_CONFIG_PATH) -> Config:
    """Load and validate the user configuration file."""
    path = Path(path)
    if not path.exists():
        raise ConfigError(
            f"Config file not found: {path}\n"
            f"Copy {EXAMPLE_CONFIG_PATH.name} to {path.name} or run "
            f"`python -m src.ui_cli` to create it."
        )

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    areas = list(raw.get("areas", []))
    keywords = list(raw.get("keywords", []))
    if not areas:
        raise ConfigError("At least one research area must be configured.")
    if not keywords:
        raise ConfigError("At least one keyword must be configured.")

    ji = raw.get("journal_inclusion", {}) or {}
    journal_inclusion = JournalInclusion(
        abs_min_level=parse_abs_level(ji.get("abs_min_level")),
        abdc_grades=[str(g).strip() for g in (ji.get("abdc_grades") or [])],
        sjr_quartile=(str(ji["sjr_quartile"]).strip() if ji.get("sjr_quartile") else None),
        include_ft50=bool(ji.get("include_ft50", True)),
        include_utd24=bool(ji.get("include_utd24", True)),
    )

    email_raw = _require(raw, "email", "config")
    email = EmailConfig(
        address=_require(email_raw, "address", "email"),
        smtp_server=_require(email_raw, "smtp_server", "email"),
        smtp_port=int(email_raw.get("smtp_port", 587)),
        smtp_username=email_raw.get("smtp_username"),
        smtp_password=email_raw.get("smtp_password"),
        from_address=email_raw.get("from_address"),
        use_tls=bool(email_raw.get("use_tls", True)),
        send_heartbeat=bool(email_raw.get("send_heartbeat", True)),
    )

    ai_raw = raw.get("ai_settings", {}) or {}
    ai_settings = AISettings(
        use_ai_agents=bool(ai_raw.get("use_ai_agents", False)),
        embedding_model=ai_raw.get("embedding_model"),
        llm_provider=ai_raw.get("llm_provider"),
        llm_model=ai_raw.get("llm_model"),
        llm_api_key=ai_raw.get("llm_api_key"),
        llm_base_url=ai_raw.get("llm_base_url"),
        ai_weight=float(ai_raw.get("ai_weight", 0.5)),
    )

    access_raw = raw.get("access", {}) or {}
    access = AccessSettings(
        proxy_url=access_raw.get("proxy_url"),
        cookies_file=access_raw.get("cookies_file"),
    )

    h_raw = raw.get("harvest", {}) or {}
    harvest = HarvestSettings(
        crossref_mailto=h_raw.get("crossref_mailto") or email.address,
        max_workers=int(h_raw.get("max_workers", 8)),
        cache_ttl_hours=int(h_raw.get("cache_ttl_hours", 24)),
        max_articles_per_journal=int(h_raw.get("max_articles_per_journal", 50)),
        enable_scraping_fallback=bool(h_raw.get("enable_scraping_fallback", True)),
        registry_file=h_raw.get("registry_file"),
        elite_only=bool(h_raw.get("elite_only", False)),
    )

    # Environment variables override secrets from the file.
    env_smtp = os.getenv("DIGEST_SMTP_PASSWORD")
    if env_smtp:
        email.smtp_password = env_smtp
    env_llm = os.getenv("DIGEST_LLM_API_KEY")
    if env_llm:
        ai_settings.llm_api_key = env_llm

    threshold = float(raw.get("relevance_threshold", 80))
    weight_factor = float(raw.get("journal_weight_factor", 0.3))
    if not 0 <= weight_factor <= 1:
        raise ConfigError("journal_weight_factor must be between 0 and 1.")

    return Config(
        areas=areas,
        keywords=keywords,
        journal_inclusion=journal_inclusion,
        relevance_threshold=threshold,
        journal_weight_factor=weight_factor,
        email=email,
        ai_settings=ai_settings,
        access=access,
        harvest=harvest,
        harvest_window_days=int(raw.get("harvest_window_days", 7)),
        raw=raw,
    )
