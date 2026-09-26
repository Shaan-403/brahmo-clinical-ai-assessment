"""Shared string-normalization helpers used across loaders."""
from __future__ import annotations
import re


def normalize_brand_key(brand_name: str) -> str:
    """Case/hyphen/whitespace-normalized brand key. Deliberately NOT a unique
    key for product identity — see products table comment and DESIGN.md D-001;
    this dataset has many brand names shared by unrelated formulations."""
    key = brand_name.upper()
    key = key.replace("-", " ")
    key = re.sub(r"\s+", " ", key).strip()
    return key


def normalize_pharmacy_billed_name(raw: str) -> str:
    """Strips pack-count and dose-form tokens from a billed pharmacy line so it
    can be compared against normalize_brand_key(brand_name). E.g.
    "MIZITH-FORTE STRIP" -> "MIZITH FORTE"; "SUPRIL-1 TAB 15'S" -> "SUPRIL 1".
    This is a deterministic cleanup, not a guess about drug identity — the
    identity question is answered later by exact/fuzzy matching against
    products, with ambiguity always queued."""
    s = raw.upper()
    s = re.sub(r"\b\d+'?\s*S\b", "", s)                       # pack counts: 15'S, 10'S, 15S
    s = re.sub(r"\b(STRIP|TAB|CAP|SYP|ML|\d+ML)\b", "", s)    # form/pack tokens
    s = s.replace("-", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s
