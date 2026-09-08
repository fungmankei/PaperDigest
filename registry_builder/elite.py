"""Create an *elite* subset of a built journals.csv.

Elite = FT50 or UTD24 or ABS/AJG rated 4*/4 or ABDC rated A*.

    python -m registry_builder.elite                         # data/journals.csv -> data/journals_elite.csv
    python -m registry_builder.elite --in X.csv --out Y.csv
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.journal_registry import (  # noqa: E402
    DEFAULT_REGISTRY_PATH,
    filter_elite,
    load_registry,
    write_registry,
)

ELITE_PATH = ROOT / "data" / "journals_elite.csv"


def _reason(j) -> str:
    bits = []
    if j.ft50:
        bits.append("FT50")
    if j.utd24:
        bits.append("UTD24")
    if j.abs_numeric is not None and j.abs_numeric >= 4.0:
        bits.append(f"ABS {j.abs_level}")
    if j.abdc and j.abdc.upper() == "A*":
        bits.append("ABDC A*")
    return ", ".join(bits)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Write the elite journal subset.")
    p.add_argument("--in", dest="src", default=str(DEFAULT_REGISTRY_PATH))
    p.add_argument("--out", dest="out", default=str(ELITE_PATH))
    args = p.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

    journals = load_registry(args.src)
    elite = filter_elite(journals)
    elite.sort(key=lambda j: j.journal_weight, reverse=True)
    write_registry(elite, args.out)

    print(f"Elite subset: {len(elite)}/{len(journals)} journals -> {args.out}\n")
    # Membership breakdown
    counts = Counter()
    for j in elite:
        if j.ft50:
            counts["FT50"] += 1
        if j.utd24:
            counts["UTD24"] += 1
        if j.abs_numeric is not None and j.abs_numeric >= 4.0:
            counts["ABS 4*/4"] += 1
        if j.abdc and j.abdc.upper() == "A*":
            counts["ABDC A*"] += 1
    print("Membership (journals may qualify via multiple lists):")
    for k in ("FT50", "UTD24", "ABS 4*/4", "ABDC A*"):
        print(f"  {k:10s}: {counts.get(k, 0)}")

    print("\nBy area:")
    areas: Counter = Counter()
    for j in elite:
        for a in (j.areas or ["(none)"]):
            areas[a] += 1
    for a, c in areas.most_common():
        print(f"  {c:4d}  {a}")

    print("\nTop 10 by weight:")
    for j in elite[:10]:
        print(f"  {j.journal_weight:5.2f}  IF={j.impact_factor:5.2f}  {j.journal_name}  [{_reason(j)}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
