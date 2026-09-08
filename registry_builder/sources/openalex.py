"""Impact-factor enrichment via the OpenAlex API (open, free, no key).

Clarivate's Journal Impact Factor (JIF) is proprietary. OpenAlex publishes an
open, JIF-like metric per source: ``summary_stats.2yr_mean_citedness`` — the
mean citations in the current year to works published in the previous two years
— which we use as an **impact-factor proxy**. We also backfill ISSNs and the
publisher from OpenAlex.
"""
from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha1
from pathlib import Path
from typing import Optional

from ..normalize import format_issn, normalize_name

log = logging.getLogger("builder.openalex")


def _name_matches(query: str, candidate: Optional[str]) -> bool:
    """True if a name-search hit is confidently the same journal."""
    if not candidate:
        return False
    q, c = normalize_name(query), normalize_name(candidate)
    if not q or not c:
        return False
    if q == c or q in c or c in q:
        return True
    qt, ct = set(q.split()), set(c.split())
    overlap = len(qt & ct) / max(1, len(qt))
    return overlap >= 0.8

OPENALEX_SOURCES = "https://api.openalex.org/sources"


def _cache_get(cache_dir: Path, key: str, ttl_hours: int) -> Optional[dict]:
    path = cache_dir / f"{sha1(key.encode()).hexdigest()}.json"
    if not path.exists() or (time.time() - path.stat().st_mtime) > ttl_hours * 3600:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _cache_put(cache_dir: Path, key: str, payload: dict) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        (cache_dir / f"{sha1(key.encode()).hexdigest()}.json").write_text(
            json.dumps(payload), encoding="utf-8")
    except OSError:  # pragma: no cover
        pass


def _extract(source: dict) -> dict:
    stats = source.get("summary_stats") or {}
    issns = [format_issn(i) for i in (source.get("issn") or [])]
    if source.get("issn_l"):
        issns = [format_issn(source["issn_l"])] + [i for i in issns if i != format_issn(source["issn_l"])]
    return {
        "impact_factor": round(float(stats.get("2yr_mean_citedness") or 0.0), 3),
        "h_index": stats.get("h_index"),
        "publisher": source.get("host_organization_name") or "",
        "issn": list(dict.fromkeys(i for i in issns if i)),
        "openalex_name": source.get("display_name"),
    }


def _get_json(url: str, params: dict, cache_dir: Path, ttl_hours: int,
              max_retries: int = 4) -> Optional[dict]:
    """GET with on-disk cache + retry/exponential backoff on 429/5xx."""
    import requests

    key = f"{url}|{sorted(params.items())}"
    cached = _cache_get(cache_dir, key, ttl_hours)
    if cached is not None:
        return cached

    delay = 1.0
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=45)
            if resp.status_code == 200:
                payload = resp.json()
                _cache_put(cache_dir, key, payload)
                return payload
            if resp.status_code == 404:
                return None
            if resp.status_code in (429, 500, 502, 503, 504):
                if attempt < max_retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
            log.debug("OpenAlex %s for %s", resp.status_code, url)
            return None
        except Exception as exc:  # noqa: BLE001
            if attempt < max_retries:
                time.sleep(delay)
                delay *= 2
                continue
            log.debug("OpenAlex request failed for %s: %s", url, exc)
    return None


def _fetch(record: dict, mailto: str, cache_dir: Path, ttl_hours: int) -> Optional[dict]:
    issns = record.get("issn") or []
    params_base = {"mailto": mailto} if mailto else {}

    # 1) Exact ISSN lookups first (most reliable).
    for issn in issns:
        payload = _get_json(f"{OPENALEX_SOURCES}/issn:{issn}", dict(params_base),
                            cache_dir, ttl_hours)
        if payload and "id" in payload:
            return _extract(payload)

    # 2) Name search fallback: scan the first few hits for a confident match.
    payload = _get_json(OPENALEX_SOURCES,
                        {**params_base, "search": record["journal_name"], "per-page": 5},
                        cache_dir, ttl_hours)
    for cand in (payload or {}).get("results", [])[:5]:
        if _name_matches(record["journal_name"], cand.get("display_name")):
            return _extract(cand)
    return None


def enrich_impact_factors(records: dict[str, dict], mailto: str,
                          cache_dir: Path, max_workers: int = 6,
                          ttl_hours: int = 168) -> int:
    """Fill impact_factor (+ publisher / ISSNs) in place. Returns count enriched."""
    enriched = 0
    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as pool:
        futures = {pool.submit(_fetch, rec, mailto, cache_dir, ttl_hours): key
                   for key, rec in records.items()}
        for fut in as_completed(futures):
            rec = records[futures[fut]]
            try:
                data = fut.result()
            except Exception:  # noqa: BLE001
                data = None
            if not data:
                continue
            rec["impact_factor"] = data["impact_factor"]
            if not rec.get("publisher") and data.get("publisher"):
                rec["publisher"] = data["publisher"]
            # merge ISSNs (seed/list ISSNs first, then any new ones from OpenAlex)
            merged = list(rec.get("issn") or [])
            for i in data.get("issn") or []:
                if i not in merged:
                    merged.append(i)
            rec["issn"] = merged
            if data["impact_factor"] > 0:
                enriched += 1
    log.info("Enriched impact factors for %d/%d journals via OpenAlex.",
             enriched, len(records))
    return enriched
