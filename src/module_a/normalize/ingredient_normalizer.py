"""Canonical ingredient (salt) registry + alias resolution.

Every raw ingredient-name string encountered anywhere in the data pack is
resolved through here, and every attempt is recorded in ingredient_aliases —
including the exact matches — so the mapping is fully auditable, not just the
uncertain ones.

Resolution tiers (see config/thresholds.yaml normalization.* and DESIGN.md
D-002 for why there is no "fuzzy auto-accept" threshold):
  1. structured_source_field — the source declares the canonical ingredient
     itself (first time CDCI mentions "Paracetamol", it becomes canonical).
  2. exact_normalized_match   — a new raw string normalizes (casefold +
     whitespace collapse) to an EXISTING canonical ingredient's key. Auto-
     resolved.
  3. fuzzy_candidate_unconfirmed — anything else. Always queued; never
     auto-merged, however high the similarity score.
"""
from __future__ import annotations
import re
import sqlite3
from datetime import datetime, timezone

from rapidfuzz import fuzz, process

from src.config import load_config
from src.module_a.review_queue.queue import add_review_item


def normalize_key(raw: str) -> str:
    key = raw.strip().casefold()
    key = re.sub(r"\s+", " ", key)
    return key


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_alias(conn: sqlite3.Connection, raw_text: str, ingredient_id: int | None,
                   confidence: float, method: str, source: str, source_version: str | None,
                   load_batch_id: int) -> int:
    cur = conn.execute(
        """
        INSERT INTO ingredient_aliases
            (raw_text, ingredient_id, confidence, method, source, source_version, load_batch_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (raw_text, ingredient_id, confidence, method, source, source_version, load_batch_id, _now()),
    )
    return cur.lastrowid


def get_or_create_canonical_ingredient(conn: sqlite3.Connection, raw_name: str, source: str,
                                        source_version: str | None, load_batch_id: int) -> int:
    """Used only by trusted, structured sources (CDCI's own ingredient columns).
    Creates a new canonical ingredient the first time a normalized key is seen;
    reuses it exactly thereafter. This never fuzzy-matches — it's the
    authoritative source declaring its own vocabulary."""
    key = normalize_key(raw_name)
    row = conn.execute("SELECT id FROM ingredients WHERE normalized_key = ?", (key,)).fetchone()
    if row:
        ingredient_id = row["id"]
        method = "structured_source_field"
        confidence = load_config()["normalization"]["structured_source_confidence"]
    else:
        cur = conn.execute(
            """
            INSERT INTO ingredients
                (canonical_name, normalized_key, first_seen_source, first_seen_source_version,
                 first_seen_load_batch_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (raw_name.strip(), key, source, source_version, load_batch_id, _now()),
        )
        ingredient_id = cur.lastrowid
        method = "structured_source_field"
        confidence = load_config()["normalization"]["structured_source_confidence"]
    _record_alias(conn, raw_name, ingredient_id, confidence, method, source, source_version, load_batch_id)
    return ingredient_id


def resolve_reference_ingredient(conn: sqlite3.Connection, raw_name: str, source: str,
                                  source_version: str | None, load_batch_id: int,
                                  entity_type_for_queue: str) -> tuple[int | None, str]:
    """Used by untrusted/secondary reference sources (NLEM, Jan Aushadhi) whose
    ingredient-name spelling is not guaranteed to match CDCI's vocabulary
    exactly. Returns (ingredient_id_or_None, match_status) where match_status
    is 'EXACT' or 'QUEUED'. Never auto-merges on a fuzzy match."""
    cfg = load_config()["normalization"]
    key = normalize_key(raw_name)

    row = conn.execute("SELECT id FROM ingredients WHERE normalized_key = ?", (key,)).fetchone()
    if row:
        ingredient_id = row["id"]
        _record_alias(conn, raw_name, ingredient_id, cfg["exact_match_confidence"],
                      "exact_normalized_match", source, source_version, load_batch_id)
        return ingredient_id, "EXACT"

    # No exact match: look for fuzzy candidates purely as evidence for a human.
    all_ingredients = conn.execute("SELECT id, canonical_name, normalized_key FROM ingredients").fetchall()
    choices = {r["normalized_key"]: r for r in all_ingredients}
    candidates = []
    if choices:
        matches = process.extract(key, list(choices.keys()), scorer=fuzz.WRatio, limit=cfg["fuzzy_top_k"])
        for matched_key, score, _ in matches:
            if score >= cfg["fuzzy_candidate_floor"]:
                r = choices[matched_key]
                candidates.append({"ingredient_id": r["id"], "canonical_name": r["canonical_name"], "score": score})

    alias_id = _record_alias(conn, raw_name, None, 0.0, "fuzzy_candidate_unconfirmed",
                              source, source_version, load_batch_id)
    reason_code = "AMBIGUOUS_INGREDIENT_ALIAS" if candidates else "NO_CANDIDATE_INGREDIENT_ALIAS"
    add_review_item(conn, entity_type=entity_type_for_queue, entity_id=alias_id,
                     reason_code=reason_code, candidates={"raw_text": raw_name, "candidates": candidates})
    return None, "QUEUED"
