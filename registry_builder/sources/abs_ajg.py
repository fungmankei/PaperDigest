"""ABS / AJG (Academic Journal Guide) — optional, user-provided file.

The ABS/AJG list is proprietary (behind a Chartered ABS login) and is therefore
NEVER downloaded. If you have licensed access, download the list and pass it via
``--abs-file``; this module parses it to enrich journals with an AJG level
(1, 2, 3, 4, 4*).
"""
from __future__ import annotations

import logging
from pathlib import Path

from ..normalize import normalize_name, split_issns
from ..tabular import find_column, read_table

log = logging.getLogger("builder.abs")

_NAME_COLS = {"journaltitle", "title", "journal", "journalname"}
_LEVEL_COLS = {"ajg2024", "ajg2021", "ajg", "abs", "abs2021", "rating",
               "ajgrating", "absrating", "level", "grade"}
_ISSN_COLS = {"issn", "issnprint", "printissn", "issnonline", "eissn"}
_FIELD_COLS = {"field", "for", "discipline", "subject", "subjectarea", "category"}


def parse_abs(path: Path) -> dict[str, dict]:
    """Parse an ABS/AJG file into {normalised_name: {abs_level, issn, name}}."""
    headers, rows = read_table(Path(path))
    name_col = find_column(headers, _NAME_COLS)
    level_col = find_column(headers, _LEVEL_COLS)
    if not name_col or not level_col:
        raise ValueError(
            f"ABS file missing title/level columns. Headers seen: {headers}")
    issn_col = find_column(headers, _ISSN_COLS)
    field_col = find_column(headers, _FIELD_COLS)

    out: dict[str, dict] = {}
    for row in rows:
        name = str(row.get(name_col) or "").strip()
        level = str(row.get(level_col) or "").strip()
        if level.endswith(".0"):          # openpyxl int cells: 4.0 -> "4"
            level = level[:-2]
        if not name or not level or level.lower() in ("na", "n/a", "-"):
            continue
        issns = split_issns(str(row.get(issn_col) or "")) if issn_col else []
        out[normalize_name(name)] = {
            "journal_name": name,
            "abs_level": level,
            "issn": issns,
            "field": str(row.get(field_col) or "").strip() if field_col else "",
        }
    log.info("Parsed %d ABS/AJG-rated journals from %s", len(out), path)
    return out
