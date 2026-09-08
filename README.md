# Weekly Journal Digest System

Automatically retrieve newly published journal articles that match your research
interests, score them for relevance, and email yourself a weekly digest.

- **Zero-cost baseline** — TF-IDF + rule-based relevance, no paid APIs.
- **Optional AI mode** — local/free embeddings (`sentence-transformers`) and
  local LLM summaries (`ollama`), or hosted providers if you opt in.
- **Article harvesting** via the free CrossRef API (with a scraping fallback).
- **Journal filtering** by ABS/AJG, FT50, UTD24, ABDC and SJR rankings.
- **Runs anywhere** — macOS, Windows, Linux, cloud servers, or GitHub Actions.

## Quick start

```bash
# 1. Install (Python 3.10+)
python -m pip install -r requirements.txt

# 2. Build your journal registry from your combined ranking file
#    (a sample is provided so you can try it immediately)
python -m src.journal_registry --build path/to/your_rankings.xlsx --sync-areas
#    ...or just use the bundled sample:
cp data/journals.sample.csv data/journals.csv     # (Windows: copy)

# 3. Configure — interactive wizard OR edit YAML by hand
python -m src.ui_cli
#    ...or:  cp config/user_config.example.yaml config/user_config.yaml  && edit

# 4. Try it without sending email
python -m src.main --dry-run

# 5. Run for real (sends the email)
python -m src.main
```

Then schedule it weekly — see [`src/automation/`](src/automation) or the
[GitHub Actions workflow](.github/workflows/weekly-digest.yml).

## Documentation

| Doc | Contents |
|-----|----------|
| [INSTALL.md](INSTALL.md) | Setup, virtualenv, optional AI dependencies |
| [USAGE.md](USAGE.md) | Configuration, running, scheduling, examples |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Modules, data flow, data structures |
| [JOURNAL_SOURCES.md](JOURNAL_SOURCES.md) | Ranking lists, combined-file format |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev setup, tests, coding standards |

## Security

- `config/user_config.yaml` and everything under `logs/`, `data/cache/`, plus
  your generated `data/journals.csv` are **git-ignored**.
- Use **email app passwords**, and prefer environment variables for secrets:
  `DIGEST_SMTP_PASSWORD`, `DIGEST_LLM_API_KEY`.
- Never commit ranking lists, API keys, proxy URLs, or cookies.

## License

See [LICENSE](LICENSE). Journal ranking lists are the property of their
respective owners and are **not** distributed with this project.
# PaperDigest
