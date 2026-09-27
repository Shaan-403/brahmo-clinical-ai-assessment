"""Semantic retrieval channel.

Tries fastembed (the configured ONNX model, config/thresholds.yaml
retrieval.fastembed_model) first. In this environment, model downloads from
the Hugging Face hub are blocked by the org's egress policy (verified: PyPI
reachable, huggingface.co returns 403 from the proxy) -- exactly the same
shape of environment constraint that already forced a dependency swap once
in this codebase (sentence-transformers -> fastembed, see requirements.txt
history). Rather than let Module B's build depend on unblocking that policy,
a deterministic, fully offline TF-IDF cosine-similarity backend is used as a
documented fallback (DESIGN.md D-016). The interface is identical either
way, and which backend actually ran is recorded per-chunk in
stw_chunk_embeddings.method and returned by build_chunk_embeddings(), never
silently substituted without a record.
"""
from __future__ import annotations
import json
import math
import sqlite3
from datetime import datetime, timezone

from src.config import load_config
from src.module_b.retrieval.tokenize import tokenize as _tokenize


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _try_fastembed():
    cfg = load_config()["retrieval"]
    from fastembed import TextEmbedding  # raises ImportError if not installed at all
    model = TextEmbedding(model_name=cfg["fastembed_model"])  # raises on a blocked/failed download

    def embed_many(texts: list[str]) -> list[list[float]]:
        return [list(v) for v in model.embed(texts)]

    return embed_many, f"fastembed:{cfg['fastembed_model']}"


def _build_tfidf_vocab(texts: list[str]) -> dict[str, float]:
    n_docs = len(texts)
    df: dict[str, int] = {}
    for text in texts:
        for term in set(_tokenize(text)):
            df[term] = df.get(term, 0) + 1
    return {term: math.log((n_docs + 1) / (count + 1)) + 1.0 for term, count in df.items()}


def _tfidf_vector(text: str, vocab_terms: list[str], idf: dict[str, float]) -> list[float]:
    tokens = _tokenize(text)
    if not tokens:
        return [0.0] * len(vocab_terms)
    tf: dict[str, float] = {}
    for t in tokens:
        tf[t] = tf.get(t, 0.0) + 1.0
    vec = [tf.get(term, 0.0) * idf.get(term, 0.0) for term in vocab_terms]
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def build_chunk_embeddings(conn: sqlite3.Connection, load_batch_id: int) -> str:
    """Embeds every chunk currently in stw_chunks and persists the vectors.
    Returns the method string actually used. Idempotent at the caller's
    discretion -- this always overwrites, since it's meant to run once per
    corpus load right after load_stw_corpus."""
    chunks = conn.execute(
        """
        SELECT c.id, c.chunk_text, c.section_heading, d.title
        FROM stw_chunks c JOIN stw_documents d ON d.id = c.document_id
        ORDER BY c.id
        """
    ).fetchall()
    # Same augmentation as the FTS index (src/module_b/chunking/stw_loader.py):
    # embed title + section heading + body, not the body alone, so the
    # semantic channel can find a chunk whose only mention of the condition
    # (e.g. "dengue") is in its document's title. stw_chunks.chunk_text
    # itself is never touched -- only what gets fed into the vector.
    texts = [f"{c['title']} {c['section_heading']} {c['chunk_text']}" for c in chunks]

    try:
        embed_many, method = _try_fastembed()
        vectors = embed_many(texts)
    except Exception:
        vocab_idf = _build_tfidf_vocab(texts)
        vocab_terms = sorted(vocab_idf)
        for term in vocab_terms:
            conn.execute("INSERT OR REPLACE INTO stw_tfidf_vocab (term, idf, load_batch_id) VALUES (?, ?, ?)",
                         (term, vocab_idf[term], load_batch_id))
        vectors = [_tfidf_vector(t, vocab_terms, vocab_idf) for t in texts]
        method = "offline_tfidf_v1"

    for chunk, vector in zip(chunks, vectors):
        conn.execute(
            "INSERT OR REPLACE INTO stw_chunk_embeddings (chunk_id, method, vector_json, dim, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (chunk["id"], method, json.dumps(vector), len(vector), _now()),
        )
    conn.commit()
    return method


def embed_query(conn: sqlite3.Connection, query_text: str) -> tuple[list[float], str]:
    """Embeds a query with whichever backend the corpus was actually indexed
    with (recorded per-chunk in stw_chunk_embeddings.method)."""
    row = conn.execute("SELECT DISTINCT method FROM stw_chunk_embeddings").fetchone()
    if row is None:
        raise RuntimeError("No chunk embeddings found -- run load_stw_corpus + build_chunk_embeddings first")
    method = row["method"]

    if method.startswith("fastembed:"):
        embed_many, _ = _try_fastembed()
        return embed_many([query_text])[0], method

    vocab_rows = conn.execute("SELECT term, idf FROM stw_tfidf_vocab ORDER BY term").fetchall()
    vocab_terms = [r["term"] for r in vocab_rows]
    idf = {r["term"]: r["idf"] for r in vocab_rows}
    return _tfidf_vector(query_text, vocab_terms, idf), method


def semantic_search(conn: sqlite3.Connection, query_text: str, top_k: int) -> list[dict]:
    query_vector, _method = embed_query(conn, query_text)
    rows = conn.execute("SELECT chunk_id, vector_json FROM stw_chunk_embeddings").fetchall()
    scored = [{"chunk_id": r["chunk_id"], "cosine": cosine(query_vector, json.loads(r["vector_json"]))}
              for r in rows]
    scored.sort(key=lambda x: x["cosine"], reverse=True)
    return scored[:top_k]
