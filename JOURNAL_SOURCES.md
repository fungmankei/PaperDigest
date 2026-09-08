# Journal Sources & Registry Format

## Ranking lists

Journal inclusion is driven by five widely used rankings. **None of these lists
are distributed with this project** — they are licensed/owned by their
publishers. You must obtain them yourself and provide a combined file.

| List | Owner | Field used |
|------|-------|-----------|
| ABS / AJG (Academic Journal Guide) | Chartered ABS | `abs_level` (1, 2, 3, 4, 4*) |
| FT50 | Financial Times | `ft50` (in list = 1) |
| UTD24 | UT Dallas | `utd24` (in list = 1) |
| ABDC Journal Quality List | Australian Business Deans Council | `abdc` (A*, A, B, C) |
| SJR (SCImago Journal Rank) | SCImago / Scopus | `sjr` (Q1–Q4) |

## Building the registry from a combined file

Provide **one file** (`.csv` or `.xlsx`) with one row per journal:

```bash
python -m src.journal_registry --build your_rankings.xlsx --sync-areas
```

This writes the canonical `data/journals.csv` (git-ignored).

### Expected columns (flexible matching)

Header names are normalised (lower-cased, punctuation/spaces removed) and matched
against these synonyms — you do **not** need exact names:

| Canonical | Recognised headers (examples) |
|-----------|-------------------------------|
| `journal_name` | journal, title, journal title, source title, name |
| `publisher` | publisher |
| `areas` | area, areas, field, discipline, subject, category |
| `issn` | issn, issns, print issn, eissn (multiple ISSN columns are merged) |
| `abs_level` | abs, ajg, abs level, ajg rating, abs2021 |
| `ft50` | ft50, ft, financial times 50 |
| `utd24` | utd24, utd, ut dallas 24 |
| `abdc` | abdc, abdc rating, abdc grade |
| `sjr` | sjr, sjr quartile, best quartile, quartile |
| `journal_weight` | journal weight, weight (optional; computed if absent) |

Notes:
- **Multi-value cells** (areas, ISSNs) may use `;` or `|` separators.
- **Boolean cells** (`ft50`, `utd24`) accept `1/0`, `yes/no`, `true/false`, `x`.
- `abs_level` `4*` is treated as `4.5` for comparisons.
- `journal_weight` is auto-computed (0–25) from the rankings when not supplied:
  `min(25, abs_level*5 + 2.5·ft50)`, falling back to ABDC/SJR when ABS is absent.

## ISSNs matter

Harvesting is most reliable when a journal has an **ISSN** — CrossRef is queried
by ISSN. Without one, the harvester falls back to a (less precise)
container-title query. Include print and/or electronic ISSNs where you can.

## Sample registry

`data/journals.sample.csv` contains ~25 top business/economics journals with
real ISSNs so you can try the system immediately. **Verify ISSNs and rankings
against the official lists before relying on the digest** — the sample is for
demonstration and may not reflect the latest editions.

## Maintenance

Rankings are revised periodically (ABDC, ABS, SJR annually; FT50/UTD24 less
often). Re-run the `--build` step with the updated combined file to refresh
`data/journals.csv`.
