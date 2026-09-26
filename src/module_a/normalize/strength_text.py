"""Parses CDCI's free-text strength_text field independently of the
structured ingredient_1/2/3 + strength_1/2/3_mg columns, so the two can be
cross-checked against each other rather than trusting the structured columns
blindly (see DESIGN.md D-006).

Example: "Paracetamol 500 mg + Chlorpheniramine 2 mg + Phenylephrine 10 mg"
       -> [("paracetamol", 500.0), ("chlorpheniramine", 2.0), ("phenylephrine", 10.0)]

Returns None (parse failure) if any segment doesn't match the expected
"<name> <number> mg" shape -- a parse failure is itself treated as a
mismatch by the caller, never silently ignored.
"""
from __future__ import annotations
import re

_SEGMENT_RE = re.compile(r"^\s*(.+?)\s+([\d.]+)\s*mg\s*$", re.IGNORECASE)


def parse_strength_text(strength_text: str) -> list[tuple[str, float]] | None:
    segments = re.split(r"\s*\+\s*", strength_text.strip())
    parsed: list[tuple[str, float]] = []
    for seg in segments:
        m = _SEGMENT_RE.match(seg)
        if not m:
            return None
        name, value = m.group(1).strip(), m.group(2)
        try:
            parsed.append((name, float(value)))
        except ValueError:
            return None
    return parsed


def as_comparable_multiset(pairs: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Order-independent comparison key: normalize name casing/whitespace,
    sort. Order in strength_text vs. the structured columns is not itself
    asserted to matter -- only whether the same (ingredient, strength) set is
    declared both ways."""
    normalized = [(name.strip().casefold(), round(value, 6)) for name, value in pairs]
    return sorted(normalized)
