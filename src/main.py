"""Weekly Journal Digest — pipeline entry point.

Run the full weekly pipeline:

    python -m src.main                 # normal run (loads config/user_config.yaml)
    python -m src.main --dry-run       # build the digest and print it (no email)
    python -m src.main --config path   # use an alternate config file

The pipeline: load config -> load & filter journals -> harvest recent articles
-> score (TF-IDF, optional AI) -> filter by threshold -> build digest -> email.
Start/end times, article counts, email status and errors are logged.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from . import __version__
from .config_loader import (
    DEFAULT_CONFIG_PATH,
    LOGS_DIR,
    Config,
    ConfigError,
    load_config,
)


def setup_logging(verbose: bool = False) -> None:
    # Ensure Unicode (e.g. em dashes in the digest) survives consoles whose
    # default code page is not UTF-8 (common on Windows: cp1252/gbk).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    root.handlers.clear()

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(fmt)
    root.addHandler(console)

    run_handler = logging.FileHandler(LOGS_DIR / "weekly_run.log", encoding="utf-8")
    run_handler.setLevel(logging.INFO)
    run_handler.setFormatter(fmt)
    root.addHandler(run_handler)

    err_handler = logging.FileHandler(LOGS_DIR / "errors.log", encoding="utf-8")
    err_handler.setLevel(logging.WARNING)
    err_handler.setFormatter(fmt)
    root.addHandler(err_handler)


log = logging.getLogger("digest.main")


def run_pipeline(cfg: Config, to_date: Optional[date] = None,
                 dry_run: bool = False, send_email: bool = True) -> int:
    """Execute the full pipeline. Returns the number of relevant articles."""
    # Imported here so `--help` and config errors don't pay heavy import costs.
    from .journal_registry import DEFAULT_REGISTRY_PATH, filter_journals, load_registry
    from .harvest import harvest_articles
    from .relevance import filter_by_threshold, score_articles
    from .ai_agents import apply_ai
    from .digest_builder import build_digest, build_heartbeat
    from .email_sender import send_digest

    start = time.time()
    now_utc = datetime.now(timezone.utc)
    week_of = to_date or now_utc.date()
    log.info("=== Weekly Journal Digest v%s starting at %s (UTC) ===",
             __version__, now_utc.isoformat(timespec="seconds"))

    registry_path = cfg.harvest.registry_file or DEFAULT_REGISTRY_PATH
    all_journals = load_registry(registry_path)
    journals = filter_journals(all_journals, cfg.areas, cfg.journal_inclusion,
                               elite_only=cfg.harvest.elite_only)
    gate = "elite-only" if cfg.harvest.elite_only else "inclusion criteria"
    log.info("Selected %d/%d journals (%s) for areas %s from %s",
             len(journals), len(all_journals), gate, cfg.areas, registry_path)
    if not journals:
        log.warning("No journals matched your areas + inclusion criteria. "
                    "Check config/areas selection and journal_inclusion.")

    articles = harvest_articles(journals, cfg, to_date=week_of)
    articles = score_articles(articles, cfg)

    if cfg.ai_settings.use_ai_agents:
        log.info("AI mode enabled — applying semantic rescore + summaries.")
        articles = apply_ai(articles, cfg, summary_limit=20)

    relevant = filter_by_threshold(articles, cfg.relevance_threshold)
    log.info("%d/%d articles meet the relevance threshold (%.0f).",
             len(relevant), len(articles), cfg.relevance_threshold)

    email_status = "not sent"
    try:
        if relevant:
            digest = build_digest(relevant, week_of=week_of)
            if send_email:
                send_digest(cfg.email, digest, dry_run=dry_run)
                email_status = "sent (digest)"
            else:
                email_status = "skipped (--no-email)"
        elif cfg.email.send_heartbeat:
            digest = build_heartbeat(week_of=week_of)
            if send_email:
                send_digest(cfg.email, digest, dry_run=dry_run)
                email_status = "sent (heartbeat)"
            else:
                email_status = "skipped (--no-email)"
        else:
            log.info("No relevant articles and heartbeat disabled — nothing to send.")
    except Exception as exc:  # noqa: BLE001 - log & report, don't crash silently
        email_status = f"FAILED ({exc})"
        log.error("Email step failed: %s", exc)

    elapsed = time.time() - start
    log.info("=== Run complete in %.1fs | journals=%d articles=%d relevant=%d | email=%s ===",
             elapsed, len(journals), len(articles), len(relevant), email_status)
    return len(relevant)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Weekly Journal Digest pipeline.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH),
                        help="Path to user_config.yaml.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Build the digest and print it instead of emailing.")
    parser.add_argument("--no-email", action="store_true",
                        help="Run the pipeline but skip the email step entirely.")
    parser.add_argument("--to-date", default=None,
                        help="End date of the harvest window (YYYY-MM-DD); default today (UTC).")
    parser.add_argument("--verbose", action="store_true", help="Debug logging.")
    args = parser.parse_args(argv)

    setup_logging(verbose=args.verbose)

    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        log.error("Configuration error: %s", exc)
        return 2

    to_date = None
    if args.to_date:
        try:
            to_date = date.fromisoformat(args.to_date)
        except ValueError:
            log.error("Invalid --to-date '%s' (expected YYYY-MM-DD).", args.to_date)
            return 2

    try:
        run_pipeline(cfg, to_date=to_date, dry_run=args.dry_run,
                     send_email=not args.no_email)
        return 0
    except Exception as exc:  # noqa: BLE001
        log.exception("Fatal error during pipeline run: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
