"""ABDC (Australian Business Deans Council) Journal Quality List.

The ABDC list is publicly available for download. This module attempts an
automatic download (best effort) and parses the file, but also accepts a
local file you have downloaded yourself. Grades are A*, A, B, C.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from ..normalize import normalize_name, split_issns
from ..tabular import find_header_row, norm_header, read_matrix

log = logging.getLogger("builder.abdc")

# The exact URL changes with each ABDC edition; override with --abdc-url.
DEFAULT_ABDC_URL = (
    "https://abdc.edu.au/wp-content/uploads/2022/06/"
    "abdc-jql-2022-v3-100522.xlsx"
)

_NAME_COLS = {"journaltitle", "title", "journal", "journalname"}
_GRADE_COLS = {"rating", "grade", "abdc", "abdcrating"}   # plus any header containing "rating"
_ISSN_COLS = {"issn", "issnprint", "printissn"}
_ISSN2_COLS = {"issnonline", "onlineissn", "eissn", "issn2"}
_FOR_COLS = {"for", "forcode", "fields", "field", "discipline"}
_PUBLISHER_COLS = {"publisher", "publishername"}


def _find(header_norms: list[str], candidates: set[str],
          contains: str | None = None) -> int | None:
    for i, n in enumerate(header_norms):
        if n in candidates or (contains and contains in n):
            return i
    return None


def download_abdc(url: str, dest: Path, timeout: int = 90) -> Optional[Path]:
    """Best-effort download of the ABDC workbook. Returns the path or None."""
    import requests
    try:
        resp = requests.get(url, timeout=timeout,
                            headers={"User-Agent": "Mozilla/5.0 JournalRegistryBuilder"})
        if resp.status_code == 200 and len(resp.content) > 1024:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(resp.content)
            log.info("Downloaded ABDC list -> %s (%d bytes)", dest, len(resp.content))
            return dest
        log.warning("ABDC download returned status %s (len %d).",
                    resp.status_code, len(resp.content))
    except Exception as exc:  # noqa: BLE001
        log.warning("ABDC download failed: %s", exc)
    return None


def parse_abdc(path: Path) -> dict[str, dict]:
    """Parse an ABDC file into {normalised_name: {abdc, issn, name, ...}}.

    Robust to leading preamble rows (the official list has a title banner above
    the real header) and to a "20xx rating" column name.
    """
    matrix = read_matrix(Path(path))
    if not matrix:
        raise ValueError(f"ABDC file is empty: {path}")
    hidx = find_header_row(matrix, {"journaltitle"}) or find_header_row(matrix, {"title"})
    header = [str(c) for c in matrix[hidx]]
    hn = [norm_header(c) for c in header]

    name_i = _find(hn, _NAME_COLS)
    grade_i = _find(hn, _GRADE_COLS, contains="rating")
    if name_i is None or grade_i is None:
        raise ValueError(f"ABDC file missing title/rating columns. Header row: {header}")
    issn_i = _find(hn, _ISSN_COLS)
    issn2_i = _find(hn, _ISSN2_COLS)
    field_i = _find(hn, _FOR_COLS)
    pub_i = _find(hn, _PUBLISHER_COLS)

    def cell(row: list, i: int | None) -> str:
        if i is None or i >= len(row) or row[i] is None:
            return ""
        return str(row[i]).strip()

    out: dict[str, dict] = {}
    for row in matrix[hidx + 1:]:
        name = cell(row, name_i)
        grade = cell(row, grade_i).upper().replace(" ", "")
        if not name or grade not in ("A*", "A", "B", "C"):
            continue
        issns = split_issns(cell(row, issn_i)) + split_issns(cell(row, issn2_i))
        out[normalize_name(name)] = {
            "journal_name": name,
            "abdc": grade,
            "issn": list(dict.fromkeys(issns)),
            "field": cell(row, field_i),
            "publisher": cell(row, pub_i),
        }
    log.info("Parsed %d ABDC-rated journals from %s", len(out), path)
    return out


def load_abdc(url: Optional[str], local_file: Optional[Path],
              cache_path: Path) -> dict[str, dict]:
    """Load ABDC data from a local file, else a download, else empty."""
    if local_file:
        return parse_abdc(Path(local_file))
    if url:
        got = download_abdc(url, cache_path)
        if got:
            return parse_abdc(got)
    if cache_path.exists():
        log.info("Using cached ABDC file %s", cache_path)
        return parse_abdc(cache_path)
    log.warning("No ABDC data available (no --abdc-file and download unavailable). "
                "Continuing without ABDC grades.")
    return {}
