"""Shared pytest fixtures and helpers."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the project root importable as `src.*` regardless of the cwd.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config_loader import (  # noqa: E402
    AISettings,
    AccessSettings,
    Config,
    EmailConfig,
    HarvestSettings,
    JournalInclusion,
)
from src.harvest import Article  # noqa: E402
from src.journal_registry import Journal  # noqa: E402


@pytest.fixture
def sample_config() -> Config:
    return Config(
        areas=["Marketing", "Information Systems"],
        keywords=["digital platforms", "causal inference"],
        journal_inclusion=JournalInclusion(
            abs_min_level=3, abdc_grades=["A*", "A"], sjr_quartile="Q1",
            include_ft50=True, include_utd24=True,
        ),
        relevance_threshold=50,
        journal_weight_factor=0.3,
        email=EmailConfig(address="test@example.com", smtp_server="smtp.test", smtp_port=587),
        ai_settings=AISettings(),
        access=AccessSettings(),
        harvest=HarvestSettings(crossref_mailto="test@example.com", enable_scraping_fallback=False),
        harvest_window_days=7,
    )


@pytest.fixture
def sample_journals() -> list[Journal]:
    return [
        Journal(journal_name="Journal of Marketing", areas=["Marketing"],
                issn=["0022-2429"], abs_level="4*", ft50=True, utd24=True,
                abdc="A*", sjr="Q1", journal_weight=25),
        Journal(journal_name="MIS Quarterly", areas=["Information Systems"],
                issn=["0276-7783"], abs_level="4*", ft50=True, utd24=True,
                abdc="A*", sjr="Q1", journal_weight=25),
        Journal(journal_name="Obscure Marketing Notes", areas=["Marketing"],
                issn=["1234-5678"], abs_level="1", ft50=False, utd24=False,
                abdc="C", sjr="Q4", journal_weight=5),
        Journal(journal_name="Journal of Physics", areas=["Physics"],
                issn=["9999-9999"], abs_level="4", ft50=False, utd24=False,
                abdc="A", sjr="Q1", journal_weight=20),
    ]


@pytest.fixture
def sample_articles() -> list[Article]:
    return [
        Article(title="Digital platforms and causal inference in markets",
                authors=["A. One", "B. Two"], journal="Journal of Marketing",
                abstract="We study digital platforms using causal inference methods.",
                keywords=["digital platforms"], journal_weight=25,
                doi="10.1/jm.1", url="http://example.com/1"),
        Article(title="A study of enzyme kinetics",
                authors=["C. Three"], journal="Journal of Marketing",
                abstract="Unrelated content about chemistry and enzymes.",
                journal_weight=25, doi="10.1/jm.2"),
    ]
