"""Merge the ranking sources into the canonical ``data/journals.csv``.

Pipeline:
  1. Seed from bundled FT50 + UTD24 (with ISSNs + areas).
  2. Enrich / extend with ABDC grades (download or local file), optional.
  3. Enrich / extend with ABS/AJG levels (local file only), optional.
  4. Enrich every journal with an impact-factor proxy from OpenAlex.
  5. Compute the journal weight (rank + FT50/UTD24 + impact factor; SJR excluded).
  6. Write data/journals.csv.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Iterable, Optional

# Allow running as `python -m registry_builder.build` from the project root and
# importing the main package's registry helpers.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.journal_registry import (  # noqa: E402
    Journal,
    compute_journal_weight,
    write_registry,
    sync_areas as sync_areas_registry,
)

from .normalize import normalize_name  # noqa: E402
from .sources.abdc import DEFAULT_ABDC_URL, load_abdc  # noqa: E402
from .sources.abs_ajg import parse_abs  # noqa: E402
from .sources.openalex import enrich_impact_factors  # noqa: E402
from .sources.seed_lists import load_seed  # noqa: E402

log = logging.getLogger("builder.build")

CACHE_DIR = ROOT / "registry_builder" / "data" / "cache"
DEFAULT_OUT = ROOT / "data" / "journals.csv"
FALLBACK_AREA = "General Business & Economics"

# Map common ABDC "Field of Research" descriptions to areas.yaml labels.
_FIELD_TO_AREA = {
    "accounting": "Accounting",
    "auditing and accountability": "Accounting",
    "banking, finance and investment": "Finance",
    "finance": "Finance",
    "economics": "Economics",
    "applied economics": "Economics",
    "econometrics": "Econometrics",
    "marketing": "Marketing",
    "business and management": "General Management",
    "management": "General Management",
    "strategy": "Strategy",
    "strategic management": "Strategy",
    "information systems": "Information Systems",
    "business information systems": "Information Systems",
    "operations research": "Operations Research & Management Science",
    "operations management": "Operations & Technology Management",
    "logistics and supply chain": "Operations & Technology Management",
    "human resources": "Human Resource Management & Employment Studies",
    "human resource management": "Human Resource Management & Employment Studies",
    "tourism": "Tourism & Hospitality Management",
    "entrepreneurship": "Entrepreneurship & Small Business Management",
    "international business": "International Business & Area Studies",
}


# ABS/AJG "Field" codes (from the AJG 2024 spreadsheet) -> areas.yaml labels.
_ABS_FIELD_TO_AREA = {
    "ACCOUNT": "Accounting",
    "BUS HIST & ECON HIST": "Business History & Economic History",
    "ECON": "Economics",
    "ENT-SBM": "Entrepreneurship & Small Business Management",
    "ETHICS-CSR-MAN": "Ethics & Governance",
    "FINANCE": "Finance",
    "HRM&EMP": "Human Resource Management & Employment Studies",
    "IB&AREA": "International Business & Area Studies",
    "INFO MAN": "Information Systems",
    "INNOV": "Innovation",
    "MDEV&EDU": "Management Development & Education",
    "MKT": "Marketing",
    "OPS&TECH": "Operations & Technology Management",
    "OR&MANSCI": "Operations Research & Management Science",
    "ORG STUD": "Organisation Studies",
    "PSYCH (GENERAL)": "Psychology (General)",
    "PSYCH (WOP-OB)": "Psychology (Organizational)",
    "PUB SEC": "Public Sector & Health Care",
    "REGIONAL STUDIES, PLANNING AND ENVIRONMENT": "Regional Studies, Planning & Environment",
    "SECTOR": "Sector Studies",
    "SOC SCI": "Social Sciences",
    "STRAT": "Strategy",
}


# ABDC uses numeric ANZSRC Field-of-Research codes. Map the 4-digit codes
# (and a 2-digit-division fallback) to areas.yaml labels.
_FOR_CODE_TO_AREA = {
    # ANZSRC 2020 — 35xx Commerce, management, tourism and services
    "3501": "Accounting", "3502": "Finance", "3503": "General Management",
    "3504": "Sector Studies",
    "3505": "Human Resource Management & Employment Studies", "3506": "Marketing",
    "3507": "Strategy", "3508": "Tourism & Hospitality Management",
    "3509": "Operations & Technology Management", "3599": "General Management",
    # 38xx Economics
    "3801": "Economics", "3802": "Econometrics", "3803": "Economics",
    "3899": "Economics",
    # 46xx Information and computing sciences
    "4609": "Information Systems",
    # ANZSRC 2008 legacy 15xx/14xx/08xx
    "1501": "Accounting", "1502": "Finance", "1503": "General Management",
    "1504": "Sector Studies", "1505": "Marketing",
    "1506": "Human Resource Management & Employment Studies", "1507": "Strategy",
    "1508": "Tourism & Hospitality Management", "1401": "Economics",
    "1402": "Economics", "1403": "Econometrics", "0806": "Information Systems",
}
_FOR_PREFIX_TO_AREA = {
    "35": "General Management", "38": "Economics", "15": "General Management",
    "14": "Economics", "46": "Information Systems", "08": "Information Systems",
    "39": "Management Development & Education", "13": "Management Development & Education",
    "44": "Social Sciences", "52": "Psychology (Organizational)",
    "17": "Psychology (Organizational)",
}


def _map_field_to_area(field: Optional[str]) -> Optional[str]:
    """Map an ABS code, an ABDC free-text field, or an ANZSRC FoR code to an area."""
    if not field:
        return None
    raw = str(field).strip()
    if raw.endswith(".0"):
        raw = raw[:-2]
    if raw.upper() in _ABS_FIELD_TO_AREA:            # exact ABS code
        return _ABS_FIELD_TO_AREA[raw.upper()]
    digits = raw.split(".")[0]
    if digits.isdigit():                             # ABDC numeric FoR code
        if digits[:4] in _FOR_CODE_TO_AREA:
            return _FOR_CODE_TO_AREA[digits[:4]]
        return _FOR_PREFIX_TO_AREA.get(digits[:2])
    f = raw.lower()
    # Check most specific (longest) keys first so e.g. "operations management"
    # is not shadowed by the shorter "management".
    for key in sorted(_FIELD_TO_AREA, key=len, reverse=True):
        if key in f:
            return _FIELD_TO_AREA[key]
    return None


def _blank_record(name: str) -> dict:
    return {
        "journal_name": name, "issn": [], "areas": [], "ft50": False,
        "utd24": False, "abs_level": None, "abdc": None, "publisher": "",
        "impact_factor": 0.0,
    }


def _merge_issns(rec: dict, issns: Iterable[str]) -> None:
    merged = list(rec.get("issn") or [])
    for i in issns or []:
        if i and i not in merged:
            merged.append(i)
    rec["issn"] = merged


def build(
    out_path: Path = DEFAULT_OUT,
    abdc_url: Optional[str] = DEFAULT_ABDC_URL,
    abdc_file: Optional[Path] = None,
    abdc_min_grades: tuple[str, ...] = ("A*", "A"),
    abs_file: Optional[Path] = None,
    abs_min_level: float = 3.0,
    mailto: str = "journal-digest@example.com",
    enrich: bool = True,
    max_workers: int = 6,
    sync_areas: bool = False,
) -> list[Journal]:
    records: dict[str, dict] = load_seed()
    log.info("Seeded %d journals from FT50/UTD24.", len(records))

    # --- ABDC ---
    try:
        abdc = load_abdc(abdc_url, Path(abdc_file) if abdc_file else None,
                         CACHE_DIR / "abdc_source")
    except Exception as exc:  # noqa: BLE001
        log.warning("ABDC processing failed (%s); continuing without it.", exc)
        abdc = {}
    grade_ok = {g.upper() for g in abdc_min_grades}
    for key, val in abdc.items():
        if key in records:
            records[key]["abdc"] = val["abdc"]
            _merge_issns(records[key], val.get("issn"))
        elif val["abdc"].upper() in grade_ok:
            rec = _blank_record(val["journal_name"])
            rec["abdc"] = val["abdc"]
            rec["publisher"] = val.get("publisher", "")
            _merge_issns(rec, val.get("issn"))
            area = _map_field_to_area(val.get("field"))
            rec["areas"] = [area] if area else [FALLBACK_AREA]
            records[key] = rec

    # --- ABS / AJG (optional local file) ---
    if abs_file:
        abs_data = parse_abs(Path(abs_file))
        for key, val in abs_data.items():
            if key in records:
                records[key]["abs_level"] = val["abs_level"]
                _merge_issns(records[key], val.get("issn"))
            else:
                from src.config_loader import parse_abs_level
                lvl = parse_abs_level(val["abs_level"])
                if lvl is not None and lvl >= abs_min_level:
                    rec = _blank_record(val["journal_name"])
                    rec["abs_level"] = val["abs_level"]
                    _merge_issns(rec, val.get("issn"))
                    area = _map_field_to_area(val.get("field"))
                    rec["areas"] = [area] if area else [FALLBACK_AREA]
                    records[key] = rec

    log.info("Total journals after merging lists: %d", len(records))

    # --- Impact factors (OpenAlex) ---
    if enrich:
        enrich_impact_factors(records, mailto, CACHE_DIR / "openalex",
                              max_workers=max_workers)
    else:
        log.info("Skipping OpenAlex enrichment (--no-enrich).")

    # --- Build Journal objects + weights ---
    journals: list[Journal] = []
    for rec in records.values():
        j = Journal(
            journal_name=rec["journal_name"],
            publisher=rec.get("publisher", ""),
            areas=rec.get("areas") or [FALLBACK_AREA],
            issn=rec.get("issn") or [],
            abs_level=rec.get("abs_level"),
            ft50=bool(rec.get("ft50")),
            utd24=bool(rec.get("utd24")),
            abdc=rec.get("abdc"),
            sjr=None,  # SJR intentionally excluded
            impact_factor=float(rec.get("impact_factor") or 0.0),
        )
        j.journal_weight = compute_journal_weight(j)
        journals.append(j)

    journals.sort(key=lambda x: x.journal_weight, reverse=True)
    write_registry(journals, out_path)
    log.info("Wrote %d journals to %s", len(journals), out_path)

    if sync_areas:
        added = sync_areas_registry(journals)
        if added:
            log.info("Added %d new area(s) to areas.yaml: %s", len(added), added)

    return journals
