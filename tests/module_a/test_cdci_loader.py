from src.module_a.ingest.cdci_loader import load_cdci


def test_loads_all_products(conn):
    result = load_cdci(conn)
    assert result["products"] == 2000
    count = conn.execute("SELECT COUNT(*) c FROM products").fetchone()["c"]
    assert count == 2000


def test_fdc_decomposition_meets_gate(conn):
    """Acceptance gate: at least 100 real FDC products decomposed to salt+strength."""
    result = load_cdci(conn)
    assert result["fdc_products"] >= 100


def test_sinarest_decomposes_into_three_ingredients(conn):
    load_cdci(conn)
    row = conn.execute(
        "SELECT id FROM products WHERE external_product_id = 'CD1021'"
    ).fetchone()
    assert row is not None, "CD1021 (Sinarest Tablet) should be loaded"
    ingredients = conn.execute(
        """
        SELECT i.canonical_name, pi.strength_mg, pi.position
        FROM product_ingredients pi JOIN ingredients i ON i.id = pi.ingredient_id
        WHERE pi.product_id = ? ORDER BY pi.position
        """,
        (row["id"],),
    ).fetchall()
    names_and_strengths = [(r["canonical_name"], r["strength_mg"]) for r in ingredients]
    assert names_and_strengths == [
        ("Paracetamol", 500.0),
        ("Chlorpheniramine", 2.0),
        ("Phenylephrine", 10.0),
    ]
    assert all(r["strength_mg"] is not None for r in ingredients), "confidence/strength must never be silently dropped"


def test_every_product_ingredient_row_has_full_provenance(conn):
    load_cdci(conn)
    rows = conn.execute("SELECT * FROM product_ingredients").fetchall()
    assert rows, "expected product_ingredients rows"
    for r in rows:
        assert r["source"] == "cdci"
        assert r["source_version"] is not None
        assert r["load_batch_id"] is not None
        assert r["confidence"] == 1.0
        assert r["method"] == "structured_source_field"


def test_brand_name_is_not_treated_as_unique(conn):
    """This dataset has 'Becet 1' as both Sertraline 100mg and Cefixime 100mg
    (different product_ids). The products table must allow this — asserting
    it here pins the assumption so a future migration doesn't accidentally
    add a UNIQUE(brand_name) constraint."""
    load_cdci(conn)
    rows = conn.execute(
        "SELECT external_product_id FROM products WHERE brand_name = 'Becet 1'"
    ).fetchall()
    assert len(rows) >= 2
