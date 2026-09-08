"""Verify a built data/journals.csv and print a health report.

    python -m registry_builder.verify [--path data/journals.csv]
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.journal_registry import DEFAULT_REGISTRY_PATH, load_registry  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Verify a built journals.csv.")
    p.add_argument("--path", default=str(DEFAULT_REGISTRY_PATH))
    args = p.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

    journals = load_registry(args.path)
    n = len(journals)
    print(f"Registry: {args.path}")
    print(f"Total journals: {n}\n")
    if not n:
        return 1

    with_issn = sum(1 for j in journals if j.issn)
    with_if = sum(1 for j in journals if j.impact_factor > 0)
    with_abs = sum(1 for j in journals if j.abs_level)
    with_area = sum(1 for j in journals if j.areas)
    ft50 = sum(1 for j in journals if j.ft50)
    utd24 = sum(1 for j in journals if j.utd24)
    zero_w = sum(1 for j in journals if j.journal_weight <= 0)

    def pct(x: int) -> str:
        return f"{x:4d} ({100*x/n:5.1f}%)"

    print("Coverage:")
    print(f"  has ISSN         : {pct(with_issn)}")
    print(f"  has impact factor: {pct(with_if)}")
    print(f"  has ABS level    : {pct(with_abs)}")
    print(f"  has area         : {pct(with_area)}")
    print(f"  FT50 / UTD24     : {ft50} / {utd24}")
    print(f"  zero weight      : {zero_w}")

    names = [j.journal_name.strip().lower() for j in journals]
    dupes = [name for name, c in Counter(names).items() if c > 1]
    print(f"  duplicate names  : {len(dupes)}")
    if dupes:
        print("    e.g.", dupes[:5])

    print("\nABS level distribution:")
    for lvl, c in sorted(Counter(j.abs_level or "-" for j in journals).items()):
        print(f"  {lvl:>3} : {c}")

    print("\nArea distribution:")
    area_counter: Counter = Counter()
    for j in journals:
        for a in (j.areas or ["(none)"]):
            area_counter[a] += 1
    for a, c in area_counter.most_common():
        print(f"  {c:4d}  {a}")

    ifs = [j.impact_factor for j in journals if j.impact_factor > 0]
    if ifs:
        ifs.sort()
        print(f"\nImpact factor (non-zero): min={ifs[0]:.2f} "
              f"median={ifs[len(ifs)//2]:.2f} max={ifs[-1]:.2f}")

    print("\nWeight range: "
          f"{min(j.journal_weight for j in journals):.2f} .. "
          f"{max(j.journal_weight for j in journals):.2f}")

    missing_if = [j.journal_name for j in journals if j.impact_factor <= 0]
    if missing_if:
        print(f"\n{len(missing_if)} journals missing an impact factor, e.g.:")
        for name in missing_if[:15]:
            print(f"  - {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
