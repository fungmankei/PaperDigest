# Usage

## 1. Build the journal registry

The ranking lists (ABS/AJG, FT50, UTD24, ABDC, SJR) are licensed and not shipped
with this project. Provide a **single combined file** (CSV or XLSX) with one row
per journal, then build the canonical `data/journals.csv`:

```bash
python -m src.journal_registry --build path/to/your_rankings.xlsx --sync-areas
```

- `--sync-areas` appends any new area labels found in your file to
  `config/areas.yaml` so they appear in the wizard.
- Column names are matched flexibly (see [JOURNAL_SOURCES.md](JOURNAL_SOURCES.md)).
- To experiment first, use the bundled sample:
  `cp data/journals.sample.csv data/journals.csv`.

## 2. Configure

### Option A — interactive wizard

```bash
python -m src.ui_cli
```

Pick areas from the numbered drop-down, enter keywords, set inclusion criteria,
threshold, email and (optionally) AI settings. Writes `config/user_config.yaml`.

### Option B — edit YAML by hand

```bash
cp config/user_config.example.yaml config/user_config.yaml
# edit config/user_config.yaml
```

Key fields (full reference in the example file):

```yaml
areas: [Marketing, Information Systems]
keywords: [digital platforms, causal inference, marketing analytics]
journal_inclusion:
  abs_min_level: 3
  abdc_grades: ["A*", "A"]
  sjr_quartile: "Q1"
  include_ft50: true
  include_utd24: true
relevance_threshold: 80
journal_weight_factor: 0.3
harvest_window_days: 7
email:
  address: "you@example.com"
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
```

**Secrets:** leave `smtp_password` blank and export it instead:

```bash
export DIGEST_SMTP_PASSWORD="your-app-password"     # Windows: setx DIGEST_SMTP_PASSWORD "..."
```

## 3. Run

```bash
python -m src.main --dry-run          # build + print digest, no email
python -m src.main --no-email         # run pipeline, skip email step
python -m src.main                    # full run: harvest, score, email
python -m src.main --to-date 2026-08-30   # set harvest window end date
python -m src.main --verbose          # debug logging
```

### What you receive

- **Top 20** articles: title, authors, journal, date, DOI, abstract, summary,
  and a relevance explanation.
- **Remaining** relevant articles: title, authors, journal.
- If nothing is relevant and `email.send_heartbeat: true`, a short
  "ran successfully" email is sent instead.

## 4. Tuning relevance

- Relevance is **content-only** (TF-IDF + keyword coverage) and **normalised per
  run**: the most relevant article each week scores 100, the rest scale relative
  to it, and articles with no keyword/content signal score 0.
- If you get **too few** articles, lower `relevance_threshold` (e.g. 30) or add
  keywords/synonyms; enabling AI mode (embeddings) also catches semantic matches
  beyond exact keywords.
- If you get **too many**, raise the threshold (e.g. 50–60).
- `journal_weight_factor` is **no longer used** — journal prestige does not
  affect relevance. Journals are already quality-gated by the (elite) registry.

## 5. Schedule it weekly

- macOS / Linux / cloud: [`src/automation/cron_instructions.md`](src/automation/cron_instructions.md)
- Windows: [`src/automation/windows_scheduler_instructions.md`](src/automation/windows_scheduler_instructions.md)
- GitHub Actions: [`.github/workflows/weekly-digest.yml`](.github/workflows/weekly-digest.yml)

## Logs

- `logs/weekly_run.log` — start/end times, journals selected, article counts,
  email status.
- `logs/errors.log` — warnings and errors only.
