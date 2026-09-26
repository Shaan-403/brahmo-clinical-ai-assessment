import pytest

from src.db.connection import get_connection, migrate
from src.module_a.ingest.cdci_loader import load_cdci
from src.module_a.ingest.reference_loader import load_nlem, load_jan_aushadhi
from src.module_a.ingest.pharmacy_loader import load_pharmacy_stock
from src.module_a.ingest.interaction_loader import load_severe_interactions
from src.module_a.regulatory.loader import load_regulatory_events


@pytest.fixture
def conn(tmp_path):
    """A fresh, migrated SQLite DB per test, isolated in pytest's tmp_path
    (never inside the repo — sidesteps the mounted-filesystem locking issue
    documented in src/db/connection.py, and keeps tests hermetic)."""
    c = get_connection(tmp_path / "test.sqlite3")
    migrate(c)
    yield c
    c.close()


@pytest.fixture
def loaded_conn(conn):
    """A DB with the full Module A pipeline already run against the real
    provided data pack, including A.5 regulatory events and the severe-
    interaction seed -- everything the Safety Rail (A.6) needs to query."""
    load_cdci(conn)
    load_nlem(conn)
    load_jan_aushadhi(conn)
    load_severe_interactions(conn)
    load_regulatory_events(conn)
    load_pharmacy_stock(conn)
    return conn
