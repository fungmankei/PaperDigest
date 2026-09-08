# Contributing

Thanks for helping improve the Weekly Journal Digest System.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pytest                   # for the test suite
```

## Project layout

```
weekly_journal_digest/
  src/                 # source modules (importable as `src.*`)
    main.py            # pipeline entry point
    config_loader.py   # config + validation
    ui_cli.py          # interactive wizard
    journal_registry.py
    harvest.py
    relevance.py
    ai_agents.py
    digest_builder.py
    email_sender.py
    automation/        # scheduling instructions
  config/              # areas.yaml, user_config.example.yaml
  data/                # journals.sample.csv (+ generated journals.csv, cache)
  logs/                # weekly_run.log, errors.log
  tests/               # pytest unit + integration tests
  .github/workflows/   # GitHub Actions weekly job
```

## Running tests

```bash
pytest -q
```

Tests use mocked CrossRef/SMTP/LLM responses and sample data — **no network or
email access is required**. Please add or update tests with any change:

- Unit tests for a module go in `tests/test_<module>.py`.
- Mock external I/O (`requests`, `smtplib`, LLM clients) — never hit real APIs.

## Coding standards

- Python 3.10+ typing (`X | None`, `list[...]`).
- Keep modules focused and side-effect free at import time.
- AI/optional dependencies must be imported lazily and degrade gracefully.
- Never log or commit secrets; keep new secrets behind env vars.
- Follow the existing docstring/logging style.

## Commit / PR guidelines

- Small, focused commits with descriptive messages (explain *why*).
- Update the relevant docs (`USAGE.md`, `ARCHITECTURE.md`, ...) when behaviour
  changes.
- Ensure `pytest -q` passes before opening a PR.

## Versioning

[Semantic Versioning](https://semver.org): MAJOR (breaking) / MINOR (features) /
PATCH (fixes). The version lives in `src/__init__.py`. Tag releases and include
release notes and sample config files.
