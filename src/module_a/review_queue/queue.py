"""The review queue: where every uncertain mapping lands, with a reason code.
Nothing in this codebase resolves an entry here automatically — that is the
whole point (binding law: no silent ambiguity)."""
from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone

VALID_REASON_CODES = {
    "AMBIGUOUS_BRAND_MULTIPLE_FORMULATIONS",  # brand name matches 2+ products with different ingredients/strengths
    "NO_EXACT_BRAND_MATCH",                   # no exact normalized-brand match; only fuzzy candidates (or none)
    "AMBIGUOUS_INGREDIENT_ALIAS",             # raw ingredient string has fuzzy candidates but no exact match
    "NO_CANDIDATE_INGREDIENT_ALIAS",          # raw ingredient string has no exact match and no fuzzy candidate either
}


def add_review_item(conn: sqlite3.Connection, entity_type: str, entity_id: int,
                     reason_code: str, candidates: dict | list | None) -> int:
    if reason_code not in VALID_REASON_CODES:
        raise ValueError(f"Unknown reason_code {reason_code!r}; add it to VALID_REASON_CODES deliberately")
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        """
        INSERT INTO review_queue (entity_type, entity_id, reason_code, candidates_json, status, created_at)
        VALUES (?, ?, ?, ?, 'OPEN', ?)
        """,
        (entity_type, entity_id, reason_code, json.dumps(candidates), now),
    )
    return cur.lastrowid


def open_items(conn: sqlite3.Connection, entity_type: str | None = None) -> list[sqlite3.Row]:
    if entity_type:
        return conn.execute(
            "SELECT * FROM review_queue WHERE status = 'OPEN' AND entity_type = ? ORDER BY id", (entity_type,)
        ).fetchall()
    return conn.execute("SELECT * FROM review_queue WHERE status = 'OPEN' ORDER BY id").fetchall()
