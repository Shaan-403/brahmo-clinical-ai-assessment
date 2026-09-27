import pytest

from src.db.connection import get_connection, migrate
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
def stw_conn(conn):
    """A DB with the real STW corpus + local protocol ingested and chunk
    embeddings built -- everything answer_question()/hybrid_search() need."""
    result = load_stw_corpus(conn)
    build_chunk_embeddings(conn, result["batch_id"])
    return conn
