"""Bundled FT50 and UTD24 lists (public facts, curated with ISSNs).

These two lists are small, fixed, and publicly known, so they are shipped with
the builder rather than downloaded. Each record seeds the registry with a
journal name, ISSN, area and FT50/UTD24 membership flags.
"""
from __future__ import annotations

import csv
from pathlib import Path

from ..normalize import normalize_name, split_issns

SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "ft50_utd24.csv"


def load_seed(path: Path = SEED_PATH) -> dict[str, dict]:
    """Return seed journals keyed by normalised name."""
    records: dict[str, dict] = {}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("journal_name") or "").strip()
            if not name:
                continue
            key = normalize_name(name)
            records[key] = {
                "journal_name": name,
                "issn": split_issns(row.get("issn", "")),
                "areas": [a.strip() for a in (row.get("area") or "").split(";") if a.strip()],
                "ft50": str(row.get("ft50", "0")).strip() in ("1", "true", "yes"),
                "utd24": str(row.get("utd24", "0")).strip() in ("1", "true", "yes"),
                "abs_level": None,
                "abdc": None,
                "publisher": "",
                "impact_factor": 0.0,
            }
    return records
