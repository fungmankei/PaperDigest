from pytest import approx

from src.harvest import Article
from src.relevance import (
    content_relevance,
    filter_by_threshold,
    normalize_scores,
    score_articles,
)


def test_content_relevance_blend():
    # max signal -> 1.0
    assert content_relevance(1.0, 1.0) == 1.0
    # no signal -> 0
    assert content_relevance(0.0, 0.0) == 0.0
    # tfidf weighted 0.75, keyword 0.25
    assert content_relevance(0.4, 0.0) == approx(0.3)
    assert content_relevance(0.0, 0.8) == approx(0.2)


def test_normalize_scores_batch_relative():
    arts = [Article(title="a", content_relevance=0.5),
            Article(title="b", content_relevance=0.25),
            Article(title="c", content_relevance=0.0)]
    normalize_scores(arts)
    assert arts[0].final_score == 100.0   # top scales to 100
    assert arts[1].final_score == 50.0
    assert arts[2].final_score == 0.0     # no signal stays 0


def test_journal_weight_not_used(sample_config):
    # Two identical-content articles with very different journal weights must
    # receive the same relevance score (prestige is excluded).
    a = Article(title="digital platforms study", abstract="digital platforms",
                journal="A", journal_weight=25)
    b = Article(title="digital platforms study", abstract="digital platforms",
                journal="B", journal_weight=1)
    score_articles([a, b], sample_config)
    assert a.final_score == b.final_score


def test_score_articles_ranks_relevant_first(sample_config, sample_articles):
    scored = score_articles(sample_articles, sample_config)
    assert scored[0].title.startswith("Digital platforms")
    assert scored[0].final_score > scored[1].final_score
    assert scored[0].final_score == 100.0   # normalised top
    assert scored[0].relevance_explanation
    assert "digital platforms" in scored[0].relevance_explanation.lower()


def test_filter_by_threshold(sample_config, sample_articles):
    scored = score_articles(sample_articles, sample_config)
    kept = filter_by_threshold(scored, 30)
    assert all(a.final_score >= 30 for a in kept)


def test_score_handles_empty():
    from src.config_loader import (AISettings, AccessSettings, Config,
                                    EmailConfig, HarvestSettings, JournalInclusion)
    cfg = Config(areas=["X"], keywords=["y"], journal_inclusion=JournalInclusion(),
                 relevance_threshold=50, journal_weight_factor=0.3,
                 email=EmailConfig(address="a@b.c", smtp_server="s"),
                 ai_settings=AISettings(), access=AccessSettings(),
                 harvest=HarvestSettings())
    assert score_articles([], cfg) == []
