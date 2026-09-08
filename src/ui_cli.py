"""Interactive configuration wizard (the CLI "drop down").

Run:

    python -m src.ui_cli

Walks the user through area selection (numbered menu derived from areas.yaml),
keywords, journal inclusion criteria, threshold, email, and AI settings, then
writes ``config/user_config.yaml``. Users who prefer may edit that YAML by hand
(copy ``user_config.example.yaml``) — both paths are supported.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from .config_loader import DEFAULT_CONFIG_PATH, EXAMPLE_CONFIG_PATH, load_areas


def _prompt(text: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    val = input(f"{text}{suffix}: ").strip()
    return val or (default or "")


def _prompt_bool(text: str, default: bool) -> bool:
    d = "Y/n" if default else "y/N"
    val = input(f"{text} [{d}]: ").strip().lower()
    if not val:
        return default
    return val in ("y", "yes", "true", "1")


def _select_areas(areas: list[str]) -> list[str]:
    if not areas:
        print("No areas.yaml found; enter areas manually (comma-separated).")
        raw = _prompt("Areas")
        return [a.strip() for a in raw.split(",") if a.strip()]

    print("\nAvailable research areas (the drop-down):")
    for i, a in enumerate(areas, 1):
        print(f"  {i:2d}. {a}")
    raw = _prompt("\nSelect areas by number (comma-separated, e.g. 11,8)")
    chosen: list[str] = []
    for token in raw.split(","):
        token = token.strip()
        if token.isdigit() and 1 <= int(token) <= len(areas):
            chosen.append(areas[int(token) - 1])
    if not chosen:
        print("No valid selection; defaulting to the first area.")
        chosen = [areas[0]]
    print(f"Selected: {', '.join(chosen)}")
    return chosen


def run_wizard(out_path: Path = DEFAULT_CONFIG_PATH) -> Path:
    print("=" * 60)
    print(" Weekly Journal Digest — configuration wizard")
    print("=" * 60)

    areas = _select_areas(load_areas())

    print("\nEnter your research-interest keywords.")
    kw_raw = _prompt("Keywords (comma-separated)", "digital platforms, causal inference")
    keywords = [k.strip() for k in kw_raw.split(",") if k.strip()]

    print("\n--- Journal inclusion criteria ---")
    abs_min = _prompt("Minimum ABS/AJG level (1-4, use 4 for 4*)", "4")
    abdc_raw = _prompt("Acceptable ABDC grades (comma-separated, blank to disable)", "A*")
    sjr = _prompt("Minimum SJR quartile (Q1-Q4, blank to disable)", "Q1")
    include_ft50 = _prompt_bool("Always include FT50 journals?", True)
    include_utd24 = _prompt_bool("Always include UTD24 journals?", True)

    threshold = _prompt("Relevance threshold (0-100)", "40")
    weight_factor = _prompt("Journal weight factor (0-1)", "0.3")
    window = _prompt("Harvest window in days", "7")

    print("\n--- Email (SMTP) ---")
    address = _prompt("Your email address", "user@example.com")
    smtp_server = _prompt("SMTP server", "smtp.gmail.com")
    smtp_port = _prompt("SMTP port", "587")
    smtp_user = _prompt("SMTP username", address)
    print("Tip: use an app password. Leave blank to set DIGEST_SMTP_PASSWORD via env var.")
    smtp_pass = _prompt("SMTP password (stored locally; blank = use env var)", "")
    heartbeat = _prompt_bool("Send a heartbeat email when no new articles?", True)

    print("\n--- AI settings (optional, local/free by default) ---")
    use_ai = _prompt_bool("Enable AI agents?", False)
    embedding_model = llm_provider = llm_model = llm_api_key = llm_base_url = None
    if use_ai:
        embedding_model = _prompt("Embedding model (sentence-transformers)", "all-MiniLM-L6-v2") or None
        print("\nLLM provider options:")
        print("  local/free: ollama")
        print("  hosted:     openai | anthropic | gemini")
        print("  presets:    openrouter | together | groq | deepseek | fireworks")
        print("  any other OpenAI-compatible endpoint: custom")
        llm_provider = _prompt("LLM provider (blank for none)", "ollama") or None
        if llm_provider:
            llm_provider = llm_provider.lower().strip()
            defaults = {
                "ollama": "llama3.2", "openai": "gpt-4o-mini",
                "anthropic": "claude-3-5-haiku-latest", "gemini": "gemini-1.5-flash",
                "openrouter": "openai/gpt-4o-mini", "groq": "llama-3.1-8b-instant",
                "deepseek": "deepseek-chat", "together": "meta-llama/Llama-3-8b-chat-hf",
                "fireworks": "accounts/fireworks/models/llama-v3p1-8b-instruct",
            }
            llm_model = _prompt("Model name", defaults.get(llm_provider, "")) or None
            if llm_provider == "custom":
                llm_base_url = _prompt("Base URL (OpenAI-compatible /v1 endpoint)", "") or None
            if llm_provider not in ("ollama",):
                print("Tip: leave the key blank to use env var DIGEST_LLM_API_KEY instead.")
                llm_api_key = _prompt(f"API key for {llm_provider} (stored locally; blank = env var)", "") or None

    config = {
        "areas": areas,
        "keywords": keywords,
        "journal_inclusion": {
            "abs_min_level": _to_num(abs_min),
            "abdc_grades": [g.strip() for g in abdc_raw.split(",") if g.strip()],
            "sjr_quartile": sjr or None,
            "include_ft50": include_ft50,
            "include_utd24": include_utd24,
        },
        "relevance_threshold": _to_num(threshold),
        "journal_weight_factor": _to_num(weight_factor),
        "harvest_window_days": int(_to_num(window) or 7),
        "email": {
            "address": address,
            "from_address": None,
            "smtp_server": smtp_server,
            "smtp_port": int(_to_num(smtp_port) or 587),
            "smtp_username": smtp_user,
            "smtp_password": smtp_pass or None,
            "use_tls": True,
            "send_heartbeat": heartbeat,
        },
        "ai_settings": {
            "use_ai_agents": use_ai,
            "embedding_model": embedding_model,
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "llm_api_key": llm_api_key,
            "llm_base_url": llm_base_url,
            "ai_weight": 0.5,
        },
        "access": {"proxy_url": None, "cookies_file": None},
        "harvest": {
            "crossref_mailto": address,
            "max_workers": 8,
            "cache_ttl_hours": 24,
            "max_articles_per_journal": 50,
            "enable_scraping_fallback": True,
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        if not _prompt_bool(f"\n{out_path} exists. Overwrite?", False):
            print("Aborted; existing config kept.")
            return out_path
    out_path.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    print(f"\nSaved configuration to {out_path}")
    print("You can re-edit it by hand at any time, or copy from "
          f"{EXAMPLE_CONFIG_PATH.name}.")
    print("Next: python -m src.main --dry-run")
    return out_path


def _to_num(value: str):
    value = (value or "").strip()
    if not value:
        return None
    try:
        f = float(value)
        return int(f) if f.is_integer() else f
    except ValueError:
        return value


if __name__ == "__main__":
    run_wizard()
