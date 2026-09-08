"""CLI for the journal registry builder.

Examples
--------
Build from bundled FT50/UTD24 + OpenAlex impact factors (works out of the box):
    python -m registry_builder

Add ABDC (A*/A) from a file you downloaded, and sync new areas:
    python -m registry_builder --abdc-file ABDC-JQL-2022.xlsx --sync-areas

Add proprietary ABS/AJG levels from your licensed file:
    python -m registry_builder --abs-file AJG2021.xlsx

Offline (skip OpenAlex enrichment):
    python -m registry_builder --no-enrich
"""
from __future__ import annotations

import argparse
import logging
import sys

from .build import DEFAULT_OUT, build
from .sources.abdc import DEFAULT_ABDC_URL


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="registry_builder",
                                description="Build data/journals.csv from the ranking lists (SJR excluded).")
    p.add_argument("--out", default=str(DEFAULT_OUT), help="Output journals.csv path.")
    p.add_argument("--abdc-file", default=None, help="Local ABDC list (.xlsx/.csv).")
    p.add_argument("--abdc-url", default=DEFAULT_ABDC_URL,
                   help="ABDC download URL (best effort). Use '' to disable download.")
    p.add_argument("--abdc-min-grade", default="A*,A",
                   help="Comma-separated ABDC grades to add as NEW journals (default: A*,A).")
    p.add_argument("--abs-file", default=None, help="Local ABS/AJG list (.xlsx/.csv), proprietary.")
    p.add_argument("--abs-min-level", type=float, default=3.0,
                   help="Minimum ABS/AJG level to add as NEW journals (default: 3).")
    p.add_argument("--mailto", default="journal-digest@example.com",
                   help="Contact email for the OpenAlex polite pool.")
    p.add_argument("--no-enrich", action="store_true", help="Skip OpenAlex impact-factor enrichment.")
    p.add_argument("--max-workers", type=int, default=6, help="Parallel OpenAlex requests.")
    p.add_argument("--sync-areas", action="store_true", help="Append new areas to config/areas.yaml.")
    p.add_argument("--verbose", action="store_true", help="Debug logging.")
    args = p.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )

    journals = build(
        out_path=args.out,
        abdc_url=(args.abdc_url or None),
        abdc_file=args.abdc_file,
        abdc_min_grades=tuple(g.strip() for g in args.abdc_min_grade.split(",") if g.strip()),
        abs_file=args.abs_file,
        abs_min_level=args.abs_min_level,
        mailto=args.mailto,
        enrich=not args.no_enrich,
        max_workers=args.max_workers,
        sync_areas=args.sync_areas,
    )

    top = journals[:10]
    print(f"\nBuilt {len(journals)} journals -> {args.out}")
    print("Top 10 by computed weight:")
    for j in top:
        print(f"  {j.journal_weight:5.2f}  IF={j.impact_factor:5.2f}  {j.journal_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
