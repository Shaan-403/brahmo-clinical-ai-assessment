from src.db.connection import migrate


def test_migrations_apply_cleanly(conn):
    # conn fixture already ran migrate() once; re-running must be a no-op.
    applied_again = migrate(conn)
    assert applied_again == []


def test_all_expected_tables_exist(conn):
    tables = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )}
    expected = {
        "load_batches", "ingredients", "ingredient_aliases", "products",
        "product_ingredients", "pharmacy_stock_items", "product_resolutions",
        "review_queue", "reference_nlem", "reference_jan_aushadhi", "schema_migrations",
    }
    assert expected <= tables


def test_migrations_are_numbered_and_sequential():
    from src.db.connection import MIGRATIONS_DIR
    names = sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql"))
    numbers = [int(n.split("_", 1)[0]) for n in names]
    assert numbers == list(range(1, len(numbers) + 1)), "migrations must be numbered with no gaps"
