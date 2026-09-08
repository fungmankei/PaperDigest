from src import ai_agents
from src.ai_agents import (
    AnthropicClient,
    GeminiClient,
    OllamaClient,
    OpenAICompatibleClient,
    _build_llm,
    _extractive_summary,
    generate_summaries,
)
from src.config_loader import AISettings
from src.harvest import Article


def test_dispatch_ollama_no_key():
    llm = _build_llm(AISettings(llm_provider="ollama", llm_model="llama3.2"))
    assert isinstance(llm, OllamaClient)


def test_dispatch_openai():
    llm = _build_llm(AISettings(llm_provider="openai", llm_api_key="sk-x"))
    assert isinstance(llm, OpenAICompatibleClient)
    assert llm.base_url == "https://api.openai.com/v1"
    assert llm.model == "gpt-4o-mini"  # default filled in


def test_dispatch_anthropic_and_gemini():
    a = _build_llm(AISettings(llm_provider="claude", llm_api_key="k"))
    assert isinstance(a, AnthropicClient)
    g = _build_llm(AISettings(llm_provider="google", llm_api_key="k"))
    assert isinstance(g, GeminiClient)


def test_dispatch_preset_sets_base_url():
    llm = _build_llm(AISettings(llm_provider="groq", llm_api_key="k"))
    assert isinstance(llm, OpenAICompatibleClient)
    assert "groq.com" in llm.base_url


def test_dispatch_custom_requires_base_url():
    assert _build_llm(AISettings(llm_provider="custom", llm_model="m")) is None
    llm = _build_llm(AISettings(llm_provider="custom", llm_model="m",
                                llm_base_url="https://x/v1", llm_api_key="k"))
    assert isinstance(llm, OpenAICompatibleClient)
    assert llm.base_url == "https://x/v1"


def test_hosted_provider_without_key_returns_none():
    assert _build_llm(AISettings(llm_provider="openai")) is None
    assert _build_llm(AISettings(llm_provider="anthropic")) is None
    assert _build_llm(AISettings(llm_provider="gemini")) is None


def test_unknown_provider_returns_none():
    assert _build_llm(AISettings(llm_provider="whatever")) is None
    assert _build_llm(AISettings(llm_provider=None)) is None


def test_openai_compatible_generate(monkeypatch):
    captured = {}

    class FakeResp:
        status_code = 200
        text = ""
        def json(self):
            return {"choices": [{"message": {"content": "  a summary  "}}]}

    def fake_post(url, headers=None, json=None, timeout=None, **kw):
        captured["url"] = url
        captured["auth"] = headers.get("Authorization")
        captured["model"] = json["model"]
        return FakeResp()

    import requests
    monkeypatch.setattr(requests, "post", fake_post)
    client = OpenAICompatibleClient("m", "sk-key", "https://api.example/v1")
    assert client.generate("hi") == "a summary"
    assert captured["url"] == "https://api.example/v1/chat/completions"
    assert captured["auth"] == "Bearer sk-key"
    assert captured["model"] == "m"


def test_generate_summaries_fallback_without_llm(sample_config):
    # No provider configured -> extractive fallback still populates summary.
    arts = [Article(title="T", abstract="First sentence here. Second one follows. Third.",
                    journal="J")]
    generate_summaries(arts, sample_config, limit=20)
    assert arts[0].summary == "First sentence here. Second one follows."


def test_extractive_summary_handles_missing():
    assert "No abstract" in _extractive_summary("No abstract available")
