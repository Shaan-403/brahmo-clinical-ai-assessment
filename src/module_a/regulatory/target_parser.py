"""Deterministic parsing of regulatory_gazette_events.csv's free-text
target_description field into a matchable ingredient set plus a separated
scope qualifier.

target_description looks like:
    "Nimesulide + Paracetamol (all strengths)"
    "Ranitidine (all products)"
    "Ibuprofen + Paracetamol (paediatric suspensions only)"
    "Ofloxacin + Ornidazole Suspension (paediatric)"

This is a *split*, not a guess: ingredient names are separated on '+' exactly
like reference_loader._split_combo does for NLEM. The trailing parenthetical,
if any, is pulled out as scope_note rather than discarded, because several of
these qualifiers narrow applicability in ways this system cannot always
verify (see classify_scope below and DESIGN.md D-009). We do not attempt to
parse anything more clever out of the qualifier than that.
"""
from __future__ import annotations
import re

_PAREN_RE = re.compile(r"\(([^)]*)\)\s*$")

# Qualifiers that explicitly do NOT narrow the target -- matched case-insensitively.
_NO_LIMITATION_NOTES = {"all strengths", "all products"}


def parse_target_description(target_description: str, target_type: str) -> tuple[list[str] | None, str | None]:
    """Returns (ingredient_names_or_None, scope_note_or_None).
    ingredient_names is None when target_type == 'PRODUCT' -- a PRODUCT-type
    event names a specific formulation, not a decomposable ingredient set,
    and this system does not attempt to match those automatically (see
    DESIGN.md D-012 / gaps_register.md)."""
    m = _PAREN_RE.search(target_description)
    scope_note = m.group(1).strip() if m else None
    body = target_description[: m.start()].strip() if m else target_description.strip()

    if target_type == "PRODUCT":
        return None, scope_note

    names = [part.strip() for part in re.split(r"\s*\+\s*", body) if part.strip()]
    return names, scope_note


def classify_scope(scope_note: str | None) -> str:
    """Returns one of:
      'UNLIMITED'   -- no scope_note, or an explicit "all strengths"/"all products"
      'SUSPENSION'  -- qualifier names a suspension/paediatric-suspension formulation;
                       resolvable deterministically against products.dose_form
      'UNVERIFIABLE' -- any other non-empty qualifier (e.g. age group with no
                       structured field to check, "specific ratio", a schedule
                       enforcement note) -- this system has no data to verify it
    """
    if not scope_note:
        return "UNLIMITED"
    normalized = scope_note.strip().casefold()
    if normalized in _NO_LIMITATION_NOTES:
        return "UNLIMITED"
    if "suspension" in normalized:
        return "SUSPENSION"
    return "UNVERIFIABLE"
