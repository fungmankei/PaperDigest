"""Journal Registry Builder — sub-project.

Extracts the journal information needed by the Weekly Journal Digest System from
the *non-SJR* ranking lists (FT50, UTD24, ABDC, and optionally ABS/AJG) and
enriches each journal with an impact-factor metric from OpenAlex, then writes
the canonical ``data/journals.csv`` consumed by the main system.

SJR is intentionally excluded.
"""

__version__ = "1.0.0"
