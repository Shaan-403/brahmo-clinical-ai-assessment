"""Module B fresh-machine entry point: applies migrations, ingests the STW
corpus + local protocol, and builds chunk embeddings. Independent of Module
A's src/module_a/ingest/run_all.py -- run both for a full fresh-machine setup
(see README.md).

Idempotent for the corpus load itself (content-hash keyed, see
src.module_b.chunking.stw_loader); embeddings are rebuilt whenever this runs
after a non-skipped corpus load."""
from __future__ import annotations
import sys

from src.db.connection import get_connection, migrate
from src.module_b.chunking.stw_loader import load_stw_corpus
from src.module_b.retrieval.semantic import build_chunk_embeddings


def main() -> None:
    conn = get_connection()
    applied = migrate(conn)
    print(f"Applied {len(applied)} migration(s): {applied or '(none pending)'}")

    corpus_result = load_stw_corpus(conn)
    tag = " (skipped, already loaded)" if corpus_result["skipped"] else ""
    print(f"STW corpus: {corpus_result['documents']} documents, {corpus_result['chunks']} chunks{tag}")

    if not corpus_result["skipped"]:
        method = build_chunk_embeddings(conn, corpus_result["batch_id"])
        print(f"Chunk embeddings built with method: {method}")
    else:
        row = conn.execute("SELECT DISTINCT method FROM stw_chunk_embeddings").fetchone()
        print(f"Chunk embeddings already present (method: {row['method'] if row else 'MISSING -- rebuild needed'})")

    conn.close()


if __name__ == "__main__":
    sys.exit(main())
