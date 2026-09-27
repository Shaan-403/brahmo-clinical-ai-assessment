import pytest

from src.db.connection import get_connection, migrate
from src.module_a.ingest.cdci_loader import load_cdci
from src.module_a.ingest.interaction_loader import load_severe_interactions
from src.module_a.ingest.pharmacy_loader import load_pharmacy_stock
from src.module_a.ingest.reference_loader import load_jan_aushadhi, load_nlem
from src.module_a.regulatory.loader import load_regulatory_events
from src.module_b.chunking.stw_loader import load_stw_corpus
from src.module_b.retrieval.semantic import build_chunk_embeddings


@pytest.fixture
def conn(tmp_path):
    """A fresh, migrated SQLite DB per test, isolated in pytest's tmp_path
    (same rationale as tests/module_a/conftest.py)."""
    c = get_connection(tmp_path / "test.sqlite3")
    migrate(c)
    yield c
    c.close()


@pytest.fixture
def full_conn(conn):
    """A DB with BOTH Module A's full drug-master/regulatory/interaction
    pipeline AND Module B's STW corpus + chunk embeddings loaded -- exactly
    what Module C's build_trace() needs, since it calls straight into both
    modules' existing code with no ingestion step of its own."""
    load_cdci(conn)
    load_nlem(conn)
    load_jan_aushadhi(conn)
    load_severe_interactions(conn)
    load_regulatory_events(conn)
    load_pharmacy_stock(conn)
    stw_result = load_stw_corpus(conn)
    build_chunk_embeddings(conn, stw_result["batch_id"])
    return conn
