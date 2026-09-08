"""Relevance Scoring Module (non-AI baseline).

Zero-cost relevance using TF-IDF vectorisation + cosine similarity against the
user's keywords, blended with a simple keyword-match signal and the journal
prestige weight. Produces a 0..100 ``final_score`` and a rule-based
explanation for every article.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .config_loader import Config
from .harvest import Article

log = logging.getLogger("digest.relevance")

# Content relevance blends TF-IDF cosine similarity with keyword coverage.
TFIDF_WEIGHT = 0.5
KEYWORD_WEIGHT = 0.5


def _article_text(article: Article) -> str:
    parts = [article.title, article.abstract or ""]
    parts += article.keywords
    return " ".join(p for p in parts if p and p != "No abstract available")


def _keyword_fraction(text: str, keywords: list[str]) -> tuple[float, list[str]]:
    """Fraction of user keywords present in the text, and which matched."""
    if not keywords:
        return 0.0, []
    lower = text.lower()
    matched = [k for k in keywords if re.search(r"\b" + re.escape(k.lower()) + r"\b", lower)]
    return len(matched) / len(keywords), matched


def content_relevance(tfidf: float, kw_fraction: float) -> float:
    """Combine TF-IDF similarity and keyword coverage into a 0..1 score."""
    return min(1.0, TFIDF_WEIGHT * tfidf + KEYWORD_WEIGHT * kw_fraction)


def normalize_scores(articles: list[Article]) -> None:
    """Set final_score (0..100) by normalising content_relevance to the batch.

    Journal prestige is NOT used. The most relevant article in the run scores
    100; the rest scale proportionally. Articles with no content signal stay 0.
    """
    max_c = max((a.content_relevance for a in articles), default=0.0)
    for a in articles:
        a.final_score = round(100.0 * a.content_relevance / max_c, 2) if max_c > 0 else 0.0


def _build_explanation(article: Article, matched: list[str], tfidf: float,
                       kw_fraction: float) -> str:
    if matched:
        head = f"matches your keyword(s): {', '.join(matched)}"
    else:
        head = "no exact keyword matches"
    return (f"Relevance {article.final_score:.0f}/100 — this article {head}, "
            f"with TF-IDF content similarity {tfidf:.2f} and "
            f"keyword coverage {kw_fraction*100:.0f}%.")


def score_articles(articles: list[Article], cfg: Config) -> list[Article]:
    """Score and rank articles by content relevance only (highest first)."""
    if not articles:
        return []

    query = " ".join(cfg.keywords)
    texts = [_article_text(a) for a in articles]

    tfidf_scores = [0.0] * len(articles)
    try:
        vectoriser = TfidfVectorizer(stop_words="english", ngram_range=(1, 2),
                                     min_df=1, sublinear_tf=True)
        matrix = vectoriser.fit_transform([query] + texts)
        sims = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
        tfidf_scores = [float(s) for s in sims]
    except ValueError:
        # Empty vocabulary (e.g. all-empty abstracts) -> rely on keyword match.
        log.warning("TF-IDF vocabulary empty; falling back to keyword matching only.")

    explain_ctx = []
    for art, text, tfidf in zip(articles, texts, tfidf_scores):
        kw_fraction, matched = _keyword_fraction(text, cfg.keywords)
        art.content_similarity = round(tfidf, 4)
        art.content_relevance = content_relevance(tfidf, kw_fraction)
        explain_ctx.append((art, matched, tfidf, kw_fraction))

    normalize_scores(articles)
    for art, matched, tfidf, kw_fraction in explain_ctx:
        art.relevance_explanation = _build_explanation(art, matched, tfidf, kw_fraction)

    articles.sort(key=lambda a: a.final_score, reverse=True)
    return articles


def filter_by_threshold(articles: list[Article], threshold: float) -> list[Article]:
    return [a for a in articles if a.final_score >= threshold]
