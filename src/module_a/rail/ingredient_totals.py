"""Shared per-ingredient cumulative-daily-total computation.

Factored out of duplicate_ingredient.py (check a) so the same arithmetic
also backs cumulative_exposure.py (check d) without a second, parallel
implementation -- see DESIGN.md D-011/D-019. This module does no clinical
judgment of any kind: it only sums milligrams already sitting in resolved
prescription items. No threshold, no verdict, nothing here can produce a
HIT.
"""
from __future__ import annotations


def compute_ingredient_totals(resolved_items: list[dict]) -> dict[int, dict]:
    """resolved_items: the `resolved` list produced by
    duplicate_ingredient._resolve_items (each with item_no, written_product,
    product_id, doses_per_day, dose_frequency_raw, and a decomposed
    `ingredients` list). Returns {ingredient_id: {canonical_name,
    contributions: {product_id: {...}}}} -- one bucket per ingredient that
    appears in at least one resolved item, keyed by product_id so the same
    product's own FDC listing an ingredient once never counts as two
    sources."""
    by_ingredient: dict[int, dict] = {}
    for item in resolved_items:
        for ing in item["ingredients"]:
            bucket = by_ingredient.setdefault(
                ing["ingredient_id"], {"canonical_name": ing["canonical_name"], "contributions": {}}
            )
            if item["product_id"] not in bucket["contributions"]:
                daily_mg = (ing["strength_mg"] * item["doses_per_day"]
                            if ing["strength_mg"] is not None and item["doses_per_day"] is not None else None)
                bucket["contributions"][item["product_id"]] = {
                    "item_no": item["item_no"], "written_product": item["written_product"],
                    "product_id": item["product_id"], "strength_mg": ing["strength_mg"],
                    "dose_frequency_raw": item["dose_frequency_raw"], "doses_per_day": item["doses_per_day"],
                    "daily_mg": daily_mg,
                }
    return by_ingredient
