"""Lexical retrieval channel: SQLite FTS5 with its built-in BM25 ranking."""
from __future__ import annotations
import re
import sqlite3


def _fts_query(text: str) -> str:
    """FTS5 query syntax treats punctuation specially; a plain user question
    is turned into an OR-of-terms query so retrieval degrades gracefully
    instead of erroring on stray punctuation (e.g. "?", "—")."""
    terms = re.findall(r"[A-Za-z0-9]+", text)
    if not terms:
        return '""'
    return " OR ".join(f'"{t}"' for t in terms)


def lexical_search(conn: sqlite3.Connection, query_text: str, top_k: int) -> list[dict]:
    """Returns [{chunk_id, raw_bm25}], raw_bm25 more negative = more relevant
    (SQLite fts5's bm25() convention) -- normalized by the hybrid combiner."""
    rows = conn.execute(
        """
        SELECT rowid AS chunk_id, bm25(stw_chunks_fts) AS raw_bm25
        FROM stw_chunks_fts
        WHERE stw_chunks_fts MATCH ?
        ORDER BY raw_bm25
        LIMIT ?
        """,
        (_fts_query(query_text), top_k),
    ).fetchall()
    return [{"chunk_id": r["chunk_id"], "raw_bm25": r["raw_bm25"]} for r in rows]
