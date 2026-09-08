"""Relevance & Summaries — optional AI Agents Module.

Default target is **local / free** models so the system stays zero-cost:

* Semantic similarity via `sentence-transformers` embeddings (e.g.
  ``all-MiniLM-L6-v2``), blended with the TF-IDF baseline.
* LLM summaries / explanations via a local `ollama` server (recommended) or a
  hosted provider (OpenAI) if the user opts in.

Everything degrades gracefully: if a model or library is unavailable the system
logs a warning and falls back to the TF-IDF baseline / an extractive summary,
so the pipeline never breaks because of AI.
"""
from __future__ import annotations

import logging
import re
from typing import Optional, Protocol

from .config_loader import AISettings, Config
from .harvest import Article
from .relevance import normalize_scores

log = logging.getLogger("digest.ai")


def ai_enabled(cfg: Config) -> bool:
    return bool(cfg.ai_settings.use_ai_agents)


# --------------------------------------------------------------------------- #
# Semantic similarity (embeddings)
# --------------------------------------------------------------------------- #
def _load_embedder(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except ImportError:
        log.warning("sentence-transformers not installed; skipping semantic rescore. "
                    "Install with: pip install sentence-transformers")
        return None
    try:
        return SentenceTransformer(model_name)
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not load embedding model '%s': %s", model_name, exc)
        return None


def semantic_rescore(articles: list[Article], cfg: Config) -> list[Article]:
    """Blend embedding similarity into each article's score (in place)."""
    model_name = cfg.ai_settings.embedding_model
    if not model_name or not articles:
        return articles
    embedder = _load_embedder(model_name)
    if embedder is None:
        return articles

    import numpy as np

    query = " ".join(cfg.keywords)
    texts = [f"{a.title}. {a.abstract}" for a in articles]
    q_emb = embedder.encode([query], normalize_embeddings=True)[0]
    doc_embs = embedder.encode(texts, normalize_embeddings=True)
    sims = doc_embs @ q_emb  # cosine (already normalised)

    w = max(0.0, min(1.0, cfg.ai_settings.ai_weight))
    for art, sem in zip(articles, np.asarray(sims).tolist()):
        # Blend embedding similarity into the (TF-IDF+keyword) content score.
        blended = (1.0 - w) * art.content_relevance + w * float(sem)
        art.content_similarity = round(float(sem), 4)
        art.content_relevance = max(0.0, min(1.0, blended))
    normalize_scores(articles)
    articles.sort(key=lambda a: a.final_score, reverse=True)
    log.info("Applied semantic rescore using '%s'.", model_name)
    return articles


# --------------------------------------------------------------------------- #
# LLM client abstraction
# --------------------------------------------------------------------------- #
class LLMClient(Protocol):
    def generate(self, prompt: str) -> Optional[str]: ...


class OllamaClient:
    """Local, free LLM via an Ollama server (http://localhost:11434)."""

    def __init__(self, model: str, host: str = "http://localhost:11434"):
        self.model = model
        self.host = host.rstrip("/")

    def generate(self, prompt: str) -> Optional[str]:
        import requests
        try:
            resp = requests.post(
                f"{self.host}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=120,
            )
            if resp.status_code == 200:
                return (resp.json().get("response") or "").strip()
            log.warning("Ollama returned %s", resp.status_code)
        except Exception as exc:  # noqa: BLE001
            log.warning("Ollama request failed: %s", exc)
        return None


class OpenAICompatibleClient:
    """Hosted LLM via any OpenAI-compatible ``/chat/completions`` endpoint.

    Works for OpenAI itself and for the many compatible services (OpenRouter,
    Together, Groq, DeepSeek, Fireworks, Azure OpenAI-compatible gateways, local
    servers such as vLLM / LM Studio, ...). Just point ``base_url`` at the
    provider and supply the matching key/model. Uses ``requests`` only — no
    vendor SDK required.
    """

    DEFAULT_BASE_URL = "https://api.openai.com/v1"

    def __init__(self, model: str, api_key: Optional[str],
                 base_url: Optional[str] = None):
        self.model = model
        self.api_key = api_key
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")

    def generate(self, prompt: str) -> Optional[str]:
        import requests
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json={"model": self.model,
                      "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.3},
                timeout=120,
            )
            if resp.status_code == 200:
                return (resp.json()["choices"][0]["message"]["content"] or "").strip()
            log.warning("LLM endpoint %s returned %s: %s",
                        self.base_url, resp.status_code, resp.text[:200])
        except Exception as exc:  # noqa: BLE001
            log.warning("LLM request to %s failed: %s", self.base_url, exc)
        return None


class AnthropicClient:
    """Hosted LLM via the Anthropic (Claude) Messages API."""

    BASE_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, model: str, api_key: str, base_url: Optional[str] = None):
        self.model = model
        self.api_key = api_key
        self.base_url = (base_url or self.BASE_URL).rstrip("/")

    def generate(self, prompt: str) -> Optional[str]:
        import requests
        try:
            resp = requests.post(
                self.base_url,
                headers={"x-api-key": self.api_key,
                         "anthropic-version": "2023-06-01",
                         "Content-Type": "application/json"},
                json={"model": self.model, "max_tokens": 1024,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=120,
            )
            if resp.status_code == 200:
                blocks = resp.json().get("content", [])
                return "".join(b.get("text", "") for b in blocks).strip()
            log.warning("Anthropic returned %s: %s", resp.status_code, resp.text[:200])
        except Exception as exc:  # noqa: BLE001
            log.warning("Anthropic request failed: %s", exc)
        return None


class GeminiClient:
    """Hosted LLM via the Google Gemini generateContent API."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, model: str, api_key: str, base_url: Optional[str] = None):
        self.model = model
        self.api_key = api_key
        self.base_url = (base_url or self.BASE_URL).rstrip("/")

    def generate(self, prompt: str) -> Optional[str]:
        import requests
        try:
            resp = requests.post(
                f"{self.base_url}/{self.model}:generateContent",
                params={"key": self.api_key},
                headers={"Content-Type": "application/json"},
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=120,
            )
            if resp.status_code == 200:
                cands = resp.json().get("candidates", [])
                if not cands:
                    return None
                parts = cands[0].get("content", {}).get("parts", [])
                return "".join(p.get("text", "") for p in parts).strip()
            log.warning("Gemini returned %s: %s", resp.status_code, resp.text[:200])
        except Exception as exc:  # noqa: BLE001
            log.warning("Gemini request failed: %s", exc)
        return None


# Providers that route through the OpenAI-compatible client, with sensible
# default base URLs so users only need to supply a key + model.
_OPENAI_COMPATIBLE_BASES = {
    "openai": OpenAICompatibleClient.DEFAULT_BASE_URL,
    "openrouter": "https://openrouter.ai/api/v1",
    "together": "https://api.together.xyz/v1",
    "groq": "https://api.groq.com/openai/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "fireworks": "https://api.fireworks.ai/inference/v1",
}
_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-latest",
    "gemini": "gemini-1.5-flash",
    "openrouter": "openai/gpt-4o-mini",
    "groq": "llama-3.1-8b-instant",
    "deepseek": "deepseek-chat",
}


def _build_llm(cfg: AISettings) -> Optional[LLMClient]:
    provider = (cfg.llm_provider or "").lower().strip()
    if not provider:
        return None

    model = cfg.llm_model
    base_url = cfg.llm_base_url

    if provider == "ollama":
        return OllamaClient(model or "llama3.2", host=base_url or "http://localhost:11434")

    if provider in ("anthropic", "claude"):
        if not cfg.llm_api_key:
            log.warning("llm_provider=%s but no API key provided.", provider)
            return None
        return AnthropicClient(model or _DEFAULT_MODELS["anthropic"], cfg.llm_api_key, base_url)

    if provider in ("gemini", "google"):
        if not cfg.llm_api_key:
            log.warning("llm_provider=%s but no API key provided.", provider)
            return None
        return GeminiClient(model or _DEFAULT_MODELS["gemini"], cfg.llm_api_key, base_url)

    # Named OpenAI-compatible providers (openai, openrouter, groq, ...).
    if provider in _OPENAI_COMPATIBLE_BASES:
        if not cfg.llm_api_key:
            log.warning("llm_provider=%s but no API key provided.", provider)
            return None
        return OpenAICompatibleClient(
            model or _DEFAULT_MODELS.get(provider, "gpt-4o-mini"),
            cfg.llm_api_key,
            base_url or _OPENAI_COMPATIBLE_BASES[provider],
        )

    # Generic escape hatch: any other OpenAI-compatible endpoint via base_url.
    if provider in ("openai-compatible", "openai_compatible", "custom", "generic"):
        if not base_url:
            log.warning("llm_provider=%s requires ai_settings.llm_base_url to be set.", provider)
            return None
        if not model:
            log.warning("llm_provider=%s requires ai_settings.llm_model to be set.", provider)
            return None
        return OpenAICompatibleClient(model, cfg.llm_api_key, base_url)

    log.warning("Unknown llm_provider '%s'; skipping LLM summaries. "
                "Supported: ollama, openai, anthropic, gemini, openrouter, together, "
                "groq, deepseek, fireworks, or 'custom' with llm_base_url.", provider)
    return None


# --------------------------------------------------------------------------- #
# Summaries / explanations
# --------------------------------------------------------------------------- #
def _extractive_summary(text: str, max_sentences: int = 2) -> str:
    if not text or text == "No abstract available":
        return "No abstract available to summarise."
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[:max_sentences]).strip()


_SUMMARY_PROMPT = (
    "You are helping a researcher triage new journal articles. In 2-3 sentences, "
    "summarise the article below for someone interested in these topics: {keywords}.\n\n"
    "Title: {title}\nJournal: {journal}\nAbstract: {abstract}\n\nSummary:"
)
_EXPLAIN_PROMPT = (
    "In one sentence, explain why this article is relevant to a researcher "
    "interested in: {keywords}.\n\nTitle: {title}\nAbstract: {abstract}\n\nRelevance:"
)


def generate_summaries(articles: list[Article], cfg: Config,
                       limit: int = 20) -> list[Article]:
    """Add AI summaries/explanations to the top ``limit`` articles.

    Falls back to an extractive summary when no LLM is available so the digest
    always has a ``summary`` field populated.
    """
    keywords = ", ".join(cfg.keywords)
    llm = _build_llm(cfg.ai_settings)

    for art in articles[:limit]:
        summary = None
        if llm is not None:
            summary = llm.generate(_SUMMARY_PROMPT.format(
                keywords=keywords, title=art.title, journal=art.journal,
                abstract=art.abstract))
            explanation = llm.generate(_EXPLAIN_PROMPT.format(
                keywords=keywords, title=art.title, abstract=art.abstract))
            if explanation:
                art.relevance_explanation = explanation
        art.summary = summary or _extractive_summary(art.abstract)
    return articles


def apply_ai(articles: list[Article], cfg: Config, summary_limit: int = 20) -> list[Article]:
    """Run the full AI pipeline when enabled: rescore then summarise top items."""
    if not ai_enabled(cfg):
        return articles
    articles = semantic_rescore(articles, cfg)
    articles = generate_summaries(articles, cfg, limit=summary_limit)
    return articles
