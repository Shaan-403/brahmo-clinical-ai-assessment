"""Resolves pharmacy_stock.csv's billed item names against the drug master.

This is the sharpest ambiguity in the whole data pack: 75% of CDCI's
product rows share a brand name with at least one other, unrelated
formulation (see DESIGN.md D-001). So "found a brand-name match" is very
different from "resolved the product" here.

Resolution logic per item:
  1. Normalize the billed name and look for an EXACT normalized-brand match
     among products.
     - Exactly one candidate            -> AUTO_RESOLVED (method=exact_normalized_brand_unique)
     - Two or more candidates           -> QUEUED (reason=AMBIGUOUS_BRAND_MULTIPLE_FORMULATIONS)
       (this is the common case: 554/783 rows in the provided file)
  2. No exact match at all              -> fuzzy search for candidates, but
     ALWAYS queue regardless of score (reason=NO_EXACT_BRAND_MATCH). Fuzzy
     matching may assist search; it is never truth.
"""
from __future__ import annotations
import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone

from rapidfuzz import fuzz, process

from src.config import load_config
from src.module_a.normalize.text import normalize_brand_key, normalize_pharmacy_billed_name
from src.module_a.review_queue.queue import add_review_item


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_resolution(conn: sqlite3.Connection, entity_id: int, resolved_product_id: int | None,
                        status: str, confidence: float | None, method: str, candidates: list[dict]) -> int:
    cur = conn.execute(
        """
        INSERT INTO product_resolutions
            (entity_type, entity_id, resolved_product_id, status, confidence, method, candidates_json, created_at)
        VALUES ('pharmacy_stock_item', ?, ?, ?, ?, ?, ?, ?)
        """,
        (entity_id, resolved_product_id, status, confidence, method, json.dumps(candidates), _now()),
    )
    return cur.lastrowid


def resolve_pharmacy_item(conn: sqlite3.Connection, item_id: int, item_name_as_billed: str) -> dict:
    cfg = load_config()["normalization"]
    cleaned_key = normalize_pharmacy_billed_name(item_name_as_billed)

    exact_matches = conn.execute(
        "SELECT id, external_product_id, brand_name, strength_text FROM products WHERE brand_name_normalized = ?",
        (cleaned_key,),
    ).fetchall()

    if len(exact_matches) == 1:
        m = exact_matches[0]
        candidates = [{"product_id": m["id"], "external_product_id": m["external_product_id"],
                       "brand_name": m["brand_name"], "strength_text": m["strength_text"], "match": "exact"}]
        _record_resolution(conn, item_id, m["id"], "AUTO_RESOLVED",
                            cfg["exact_match_confidence"], "exact_normalized_brand_unique", candidates)
        return {"status": "AUTO_RESOLVED", "product_id": m["id"]}

    if len(exact_matches) >= 2:
        candidates = [{"product_id": m["id"], "external_product_id": m["external_product_id"],
                       "brand_name": m["brand_name"], "strength_text": m["strength_text"], "match": "exact"}
                      for m in exact_matches]
        _record_resolution(conn, item_id, None, "QUEUED_FOR_REVIEW", None,
                            "exact_normalized_brand_ambiguous", candidates)
        add_review_item(conn, "pharmacy_stock_item", item_id,
                         "AMBIGUOUS_BRAND_MULTIPLE_FORMULATIONS",
                         {"item_name_as_billed": item_name_as_billed, "cleaned_key": cleaned_key,
                          "candidates": candidates})
        return {"status": "QUEUED_FOR_REVIEW", "reason": "AMBIGUOUS_BRAND_MULTIPLE_FORMULATIONS",
                "n_candidates": len(candidates)}

    # No exact match at all: fuzzy search, purely as evidence. Never auto-resolved.
    all_products = conn.execute(
        "SELECT id, external_product_id, brand_name, brand_name_normalized, strength_text FROM products"
    ).fetchall()
    by_key = defaultdict(list)
    for p in all_products:
        by_key[p["brand_name_normalized"]].append(p)

    candidates = []
    if by_key:
        matches = process.extract(cleaned_key, list(by_key.keys()), scorer=fuzz.WRatio, limit=cfg["fuzzy_top_k"])
        for matched_key, score, _ in matches:
            if score >= cfg["fuzzy_candidate_floor"]:
                for p in by_key[matched_key]:
                    candidates.append({"product_id": p["id"], "external_product_id": p["external_product_id"],
                                        "brand_name": p["brand_name"], "strength_text": p["strength_text"],
                                        "match": "fuzzy", "score": score})

    _record_resolution(conn, item_id, None, "QUEUED_FOR_REVIEW", None, "fuzzy_candidate_unconfirmed", candidates)
    reason = "NO_EXACT_BRAND_MATCH"
    add_review_item(conn, "pharmacy_stock_item", item_id, reason,
                     {"item_name_as_billed": item_name_as_billed, "cleaned_key": cleaned_key,
                      "candidates": candidates})
    return {"status": "QUEUED_FOR_REVIEW", "reason": reason, "n_candidates": len(candidates)}
