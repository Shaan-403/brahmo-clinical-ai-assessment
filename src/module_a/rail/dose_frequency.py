"""Deterministic parse of the seed prescriptions' free-text dose_frequency
column (e.g. "1-0-1 x 5d", "0-0-1", "SOS") into a doses-per-day count.

Only the leading "morning-afternoon-night" triplet is interpreted; a
duration suffix ("x 5d") is not needed for a per-day total and is ignored.
Anything that doesn't start with that triplet -- most importantly "SOS"
(as-needed, no fixed daily count) -- returns None. None is a first-class
result here, not an error: per the engineering decision, an uninterpretable
frequency must be surfaced as unknown/partial, never silently treated as
zero doses per day (see DESIGN.md D-011)."""
from __future__ import annotations
import re

_FREQ_RE = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)")


def parse_doses_per_day(dose_frequency: str | None) -> int | None:
    if not dose_frequency:
        return None
    m = _FREQ_RE.match(dose_frequency)
    if not m:
        return None
    return sum(int(g) for g in m.groups())
