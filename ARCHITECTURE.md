# Architecture

## Overview

The system is composed of six modules that run as a linear weekly pipeline.

```
config/user_config.yaml ─┐
config/areas.yaml        ├─> [A] config_loader ─┐
data/journals.csv ───────┘                      │
                                                 v
                    [B] journal_registry ──> filtered journals
                                                 │
                                                 v
                    [C] harvest (CrossRef + scrape) ──> Article[]
                                                 │
                                                 v
              [D] relevance (TF-IDF)  ──(optional)──> ai_agents
                                                 │
                                                 v
                    filter by relevance_threshold
                                                 │
                                                 v
                    [E] digest_builder ──> Digest(html, text)
                                                 │
                                                 v
                    [E] email_sender (SMTP)  ──> your inbox

        [F] automation (cron / Task Scheduler / GitHub Actions)
            triggers `python -m src.main` weekly
```

## Modules

| # | Module | File | Responsibility |
|---|--------|------|----------------|
| A | User Configuration | `src/config_loader.py`, `src/ui_cli.py` | Load/validate `user_config.yaml`; interactive wizard; env-var secret overrides |
| B | Journal Registry & Ranking | `src/journal_registry.py` | Load `journals.csv`; filter by rankings + areas; build registry from a combined ranking file; compute journal weight |
| C | Article Harvesting | `src/harvest.py` | CrossRef API with retry/backoff + 24h cache; parallel fetch; BeautifulSoup abstract fallback |
| D | Relevance & AI Agents | `src/relevance.py`, `src/ai_agents.py` | TF-IDF cosine + keyword match + journal weight → `final_score`; optional embeddings + LLM summaries |
| E | Digest & Email | `src/digest_builder.py`, `src/email_sender.py` | Build HTML/plain-text digest (top 20 full + rest brief); send via SMTP with retry + console fallback |
| F | Workflow Automation | `src/automation/`, `.github/workflows/` | Weekly scheduling on macOS/Windows/Linux/cloud + GitHub Actions |

## Relevance scoring

For each article a **content relevance** in `[0, 1]` is computed from:

```
content = 0.75 * tfidf_cosine(keywords, title+abstract+keywords)
        + 0.25 * fraction_of_keywords_matched
```

The **final score** (0–100) is the content relevance **normalised to the batch**
— the most relevant article in a run scores 100 and the rest scale
proportionally; articles with no content signal stay 0:

```
final_score = 100 * content / max(content over all harvested articles)
```

Journal prestige (`journal_weight`) is **not** part of relevance — it is
retained in the registry for reference only. Because the score is batch-relative
(top = 100), a threshold around 40 is a reasonable default.

In **AI mode**, embedding cosine similarity replaces/blends with the TF-IDF
component (weight = `ai_settings.ai_weight`) and an LLM writes the per-article
summary and explanation. The LLM provider is pluggable and called over HTTP (no
vendor SDKs): `ollama` (local/free), `openai`, `anthropic`, `gemini`, presets
(`openrouter`/`together`/`groq`/`deepseek`/`fireworks`), or `custom` with a
user-supplied `llm_base_url` for any OpenAI-compatible endpoint. Keys come from
`ai_settings.llm_api_key` or the `DIGEST_LLM_API_KEY` env var. Everything
degrades gracefully to the baseline / an extractive summary if AI
libraries/models/keys are unavailable.

Articles with `final_score >= relevance_threshold` are included in the digest.

## Data structures

**Article** (`src/harvest.py`) — mirrors spec §4.3:
`title, authors[], journal, doi, publication_date, abstract, keywords[], url,
issn[], content_similarity, journal_weight, final_score, summary,
relevance_explanation`.

**Journal** (`src/journal_registry.py`) — mirrors spec §4.2:
`journal_name, publisher, areas[], issn[], abs_level, ft50, utd24, abdc, sjr,
journal_weight`.

**Digest** (`src/digest_builder.py`): `subject, html, text, total, top_count`.

## Error handling (spec §5)

- **API errors:** up to 3 retries with exponential backoff; failures logged with
  timestamps; a repeatedly failing journal is skipped (returns no articles).
- **Scraping errors:** missing meta tags → fall back to CrossRef abstract;
  failures logged at debug level.
- **Email errors:** one retry, then a console fallback message + `errors.log`.
- **Missing metadata:** absent abstract → `"No abstract available"`; absent
  keywords → relevance relies on title + abstract only.

## Performance (spec §8)

- CrossRef responses cached on disk for 24h (`data/cache/`).
- Journals fetched in parallel with `concurrent.futures.ThreadPoolExecutor`.
- A single TF-IDF vectoriser is fit once per run over all articles.
