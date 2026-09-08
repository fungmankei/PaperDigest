"""Name/ISSN normalisation helpers shared across the builder sources."""
from __future__ import annotations

import re

_LEADING_ARTICLE = re.compile(r"^(the|a|an)\s+")


def normalize_name(name: str) -> str:
    """Canonical key for matching journal titles across lists.

    Lower-cases, maps ``&`` -> ``and``, drops a leading article, and removes
    punctuation so e.g. "The Review of Financial Studies" and
    "Review of Financial Studies" collapse to the same key.
    """
    if not name:
        return ""
    s = name.strip().lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    s = _LEADING_ARTICLE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def format_issn(raw: str) -> str:
    """Normalise an ISSN to ``XXXX-XXXX`` (uppercase X check digit)."""
    if not raw:
        return ""
    digits = re.sub(r"[^0-9xX]", "", str(raw)).upper()
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:]}"
    return raw.strip()


def split_issns(raw: str) -> list[str]:
    """Split a possibly multi-valued ISSN cell into normalised ISSNs."""
    if not raw:
        return []
    parts = re.split(r"[;,|/ ]+", str(raw))
    out = [format_issn(p) for p in parts if p.strip()]
    # keep only well-formed ISSNs, de-duped, order preserved
    seen: set[str] = set()
    result = []
    for i in out:
        if re.fullmatch(r"\d{4}-\d{3}[0-9xX]", i) and i not in seen:
            seen.add(i)
            result.append(i)
    return result
