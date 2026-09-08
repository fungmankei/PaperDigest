# Journal Registry Builder

A sub-project that generates the main system's `data/journals.csv` by extracting
journal information from the ranking lists — **excluding SJR** — and folding an
**impact-factor** metric into each journal's weight.

## Sources

| Source | How it's obtained | Contributes |
|--------|-------------------|-------------|
| **FT50** | bundled (`data/ft50_utd24.csv`) | membership flag, ISSN, area |
| **UTD24** | bundled (`data/ft50_utd24.csv`) | membership flag, ISSN, area |
| **ABDC** | auto-download (best effort) or `--abdc-file` | A*/A/B/C grade, extra journals |
| **ABS / AJG** | `--abs-file` only (proprietary, never downloaded) | AJG level 1–4/4* |
| **OpenAlex** | auto (open API, no key) | **impact factor** proxy, publisher, ISSNs |
| ~~SJR~~ | **excluded by design** | — |

### Impact factor

Clarivate's Journal Impact Factor is proprietary. This builder uses OpenAlex's
open, JIF-like metric `summary_stats.2yr_mean_citedness` (mean citations this
year to the prior two years' articles) as an **impact-factor proxy**, stored in
the `impact_factor` column.

## Journal-weight formula

Defined in the main package (`src/journal_registry.compute_journal_weight`) and
reused here. Each journal's weight (0–25) blends three sub-scores:

```
weight = 25 * ( 0.60 * rank      # ABS level, else ABDC grade, else list membership
              + 0.15 * elective  # (FT50 + UTD24) / 2
              + 0.25 * impact )  # min(1, impact_factor / 15)
```

SJR is not part of the formula.

## Usage

```bash
# Works out of the box: FT50/UTD24 + OpenAlex impact factors
python -m registry_builder

# Add ABDC (A*/A) from a file you downloaded, and register any new areas
python -m registry_builder --abdc-file ABDC-JQL-2022.xlsx --sync-areas

# Add proprietary ABS/AJG levels
python -m registry_builder --abs-file AJG2021.xlsx

# Offline (skip OpenAlex)
python -m registry_builder --no-enrich
```

Run from the **project root** (the directory containing `src/` and this folder).
Output goes to `../data/journals.csv` by default.

### Key options

- `--abdc-file PATH` — local ABDC workbook (`.xlsx`/`.csv`). Column names are
  matched flexibly (title / rating / ISSN / field).
- `--abdc-url URL` — override the download URL (`''` disables downloading).
- `--abdc-min-grade A*,A` — which ABDC grades to add as *new* journals.
- `--abs-file PATH` — local ABS/AJG file (proprietary; supply your own).
- `--abs-min-level 3` — minimum AJG level to add as *new* journals.
- `--no-enrich` — skip OpenAlex (impact factors stay 0).
- `--sync-areas` — append newly seen areas to `config/areas.yaml`.
- `--mailto you@example.com` — OpenAlex polite-pool contact.

## Notes

- SJR's official download is behind a Cloudflare bot challenge and cannot be
  fetched programmatically — another reason it is excluded here.
- OpenAlex responses are cached under `data/cache/` for a week.
- The ABDC download URL changes each edition; if the default 404s, download the
  file in a browser and pass `--abdc-file`.
