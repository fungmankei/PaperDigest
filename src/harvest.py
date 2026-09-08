"""Article Harvesting Module.

Retrieves newly published article metadata, primarily via the CrossRef REST API
(free, no key required), with:

* retry + exponential backoff on transient API errors,
* on-disk response caching (default 24h),
* parallel fetching across journals (``concurrent.futures``),
* a best-effort scraping fallback (requests + BeautifulSoup) to fill in a
  missing abstract from an article's landing page ``<meta>`` tags.
"""
from __future__ import annotations

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from hashlib import sha1
from pathlib import Path
from typing import Optional

import requests

from .config_loader import DATA_DIR, Config
from .journal_registry import Journal

log = logging.getLogger("digest.harvest")

CROSSREF_WORKS = "https://api.crossref.org/works"
CACHE_DIR = DATA_DIR / "cache"
USER_AGENT = "WeeklyJournalDigest/1.0 (https://github.com/; mailto:{mailto})"

_SELECT_FIELDS = ",".join(
    ["title", "author", "container-title", "DOI", "URL", "issued",
     "published", "published-online", "published-print", "abstract",
     "subject", "ISSN"]
)


@dataclass
class Article:
    title: str
    authors: list[str] = field(default_factory=list)
    journal: str = ""
    doi: Optional[str] = None
    publication_date: Optional[str] = None
    abstract: str = "No abstract available"
    keywords: list[str] = field(default_factory=list)
    url: Optional[str] = None
    issn: list[str] = field(default_factory=list)
    # Scoring fields (populated later by relevance / ai modules)
    content_similarity: float = 0.0
    content_relevance: float = 0.0   # pre-normalisation content score (0..1)
    journal_weight: float = 0.0      # kept for reference; NOT used in relevance
    final_score: float = 0.0
    summary: Optional[str] = None
    relevance_explanation: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _strip_jats(text: Optional[str]) -> str:
    if not text:
        return "No abstract available"
    text = re.sub(r"<[^>]+>", " ", text)          # remove JATS/HTML tags
    text = re.sub(r"\s+", " ", text).strip()
    return text or "No abstract available"


def _parse_date_parts(item: dict) -> Optional[str]:
    for key in ("published", "published-online", "published-print", "issued"):
        dp = (item.get(key) or {}).get("date-parts") or []
        if dp and dp[0] and dp[0][0]:
            parts = dp[0] + [1, 1]  # pad missing month/day
            y, m, d = parts[0], parts[1], parts[2]
            try:
                return date(int(y), int(m), int(d)).isoformat()
            except (ValueError, TypeError):
                return f"{y:04d}"
    return None


def _authors(item: dict) -> list[str]:
    out = []
    for a in item.get("author", []) or []:
        name = " ".join(p for p in [a.get("given"), a.get("family")] if p)
        out.append(name or a.get("name", "").strip())
    return [n for n in out if n]


def _item_to_article(item: dict) -> Optional[Article]:
    titles = item.get("title") or []
    title = titles[0].strip() if titles else ""
    if not title:
        return None
    containers = item.get("container-title") or []
    return Article(
        title=title,
        authors=_authors(item),
        journal=containers[0].strip() if containers else "",
        doi=item.get("DOI"),
        publication_date=_parse_date_parts(item),
        abstract=_strip_jats(item.get("abstract")),
        keywords=[s.strip() for s in (item.get("subject") or []) if s],
        url=item.get("URL"),
        issn=item.get("ISSN") or [],
    )


# --------------------------------------------------------------------------- #
# Caching
# --------------------------------------------------------------------------- #
def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{sha1(key.encode()).hexdigest()}.json"


def _cache_get(key: str, ttl_hours: int) -> Optional[dict]:
    path = _cache_path(key)
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > ttl_hours * 3600:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _cache_put(key: str, payload: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        _cache_path(key).write_text(json.dumps(payload), encoding="utf-8")
    except OSError:  # pragma: no cover - non-fatal
        log.warning("Failed to write cache for %s", key)


# --------------------------------------------------------------------------- #
# HTTP with retry + exponential backoff
# --------------------------------------------------------------------------- #
def _request_json(
    url: str,
    params: dict,
    mailto: str,
    proxies: Optional[dict] = None,
    max_retries: int = 3,
) -> Optional[dict]:
    headers = {"User-Agent": USER_AGENT.format(mailto=mailto or "anonymous")}
    delay = 1.0
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, params=params, headers=headers,
                                timeout=30, proxies=proxies)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 500, 502, 503, 504):
                log.warning("CrossRef %s (attempt %d/%d) for %s",
                            resp.status_code, attempt, max_retries, url)
            else:
                log.error("CrossRef returned %s for %s", resp.status_code, url)
                return None
        except requests.RequestException as exc:
            log.warning("Request error (attempt %d/%d): %s", attempt, max_retries, exc)
        if attempt < max_retries:
            time.sleep(delay)
            delay *= 2  # exponential backoff
    log.error("Giving up on %s after %d attempts", url, max_retries)
    return None


# --------------------------------------------------------------------------- #
# Per-journal harvest
# --------------------------------------------------------------------------- #
def _crossref_filter(from_date: date, to_date: date, issns: list[str]) -> str:
    parts = [f"from-pub-date:{from_date.isoformat()}",
             f"until-pub-date:{to_date.isoformat()}"]
    parts += [f"issn:{i}" for i in issns]
    return ",".join(parts)


def harvest_journal(
    journal: Journal,
    from_date: date,
    to_date: date,
    cfg: Config,
    proxies: Optional[dict] = None,
) -> list[Article]:
    """Fetch recent articles for one journal from CrossRef (cached)."""
    mailto = cfg.harvest.crossref_mailto or ""
    rows = cfg.harvest.max_articles_per_journal

    if journal.issn:
        cr_filter = _crossref_filter(from_date, to_date, journal.issn)
        params = {"filter": cr_filter, "rows": rows, "select": _SELECT_FIELDS,
                  "sort": "published", "order": "desc"}
        if mailto:
            params["mailto"] = mailto
    else:
        # No ISSN: fall back to a container-title query (less precise).
        params = {
            "query.container-title": journal.journal_name,
            "filter": f"from-pub-date:{from_date.isoformat()},until-pub-date:{to_date.isoformat()}",
            "rows": rows, "select": _SELECT_FIELDS, "sort": "published", "order": "desc",
        }
        if mailto:
            params["mailto"] = mailto

    cache_key = f"{journal.journal_name}|{sorted(journal.issn)}|{from_date}|{to_date}|{rows}"
    payload = _cache_get(cache_key, cfg.harvest.cache_ttl_hours)
    if payload is None:
        payload = _request_json(CROSSREF_WORKS, params, mailto, proxies)
        if payload is None:
            return []  # journal skipped after repeated failures
        _cache_put(cache_key, payload)

    items = (payload.get("message") or {}).get("items", [])
    articles: list[Article] = []
    for item in items:
        art = _item_to_article(item)
        if art is None:
            continue
        # Prefer the registry journal name / weight for consistency downstream.
        art.journal = journal.journal_name
        art.journal_weight = journal.journal_weight
        if not art.issn:
            art.issn = journal.issn
        articles.append(art)

    if cfg.harvest.enable_scraping_fallback:
        for art in articles:
            if art.abstract == "No abstract available" and art.url:
                scraped = scrape_abstract(art.url, proxies)
                if scraped:
                    art.abstract = scraped
    return articles


def scrape_abstract(url: str, proxies: Optional[dict] = None) -> Optional[str]:
    """Best-effort abstract scrape from an article landing page meta tags."""
    try:
        from bs4 import BeautifulSoup  # local import: optional at import time
    except ImportError:  # pragma: no cover
        return None
    try:
        resp = requests.get(url, timeout=20, proxies=proxies,
                            headers={"User-Agent": "Mozilla/5.0 WeeklyJournalDigest"})
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        for attr, val in (("name", "citation_abstract"),
                          ("name", "dc.Description"),
                          ("property", "og:description"),
                          ("name", "description")):
            tag = soup.find("meta", attrs={attr: val})
            if tag and tag.get("content"):
                text = _strip_jats(tag["content"])
                if len(text) > 40:
                    return text
    except requests.RequestException as exc:
        log.debug("Scrape fallback failed for %s: %s", url, exc)
    return None


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def _dedupe(articles: list[Article]) -> list[Article]:
    seen: set[str] = set()
    out: list[Article] = []
    for a in articles:
        key = (a.doi or "").lower() or f"{a.title.lower()}|{a.journal.lower()}"
        if key in seen:
            continue
        seen.add(key)
        out.append(a)
    return out


def harvest_articles(
    journals: list[Journal],
    cfg: Config,
    to_date: Optional[date] = None,
) -> list[Article]:
    """Harvest recent articles across all journals in parallel."""
    to_date = to_date or datetime.now(timezone.utc).date()
    from_date = to_date - timedelta(days=cfg.harvest_window_days)
    proxies = {"http": cfg.access.proxy_url, "https": cfg.access.proxy_url} if cfg.access.proxy_url else None

    log.info("Harvesting %d journals for %s .. %s", len(journals), from_date, to_date)
    results: list[Article] = []
    with ThreadPoolExecutor(max_workers=max(1, cfg.harvest.max_workers)) as pool:
        futures = {
            pool.submit(harvest_journal, j, from_date, to_date, cfg, proxies): j
            for j in journals
        }
        for fut in as_completed(futures):
            j = futures[fut]
            try:
                arts = fut.result()
                results.extend(arts)
                log.info("  %-45s %d article(s)", j.journal_name[:45], len(arts))
            except Exception as exc:  # noqa: BLE001 - isolate per-journal failures
                log.error("Harvest failed for %s: %s", j.journal_name, exc)

    deduped = _dedupe(results)
    log.info("Harvested %d unique article(s) (%d before de-dupe)", len(deduped), len(results))
    return deduped
