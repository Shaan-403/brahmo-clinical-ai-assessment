"""Hybrid retrieval: combines the lexical (FTS5-driven) and semantic
channels, then applies metadata filtering. Structured facts (drug identity,
regulatory status) are never retrieved through this path at all -- Module A
answers those directly (brief requirement); this module only ever returns
STW/local-protocol text chunks.

Both channel scores are on an ABSOLUTE 0..1 scale, not normalized relative
to whatever happened to be retrieved -- min-max-over-the-pool normalization
was tried first and rejected: it always stretches the best candidate in any
result set towards 1.0, even for a totally unrelated query (e.g. "migraine"
against a corpus with zero migraine content), which silently defeats
abstention. See DESIGN.md D-017.
  - lexical_score  = IDF-weighted coverage of the query's terms found in
    the chunk (title+heading+body), 0..1 (FTS5 MATCH still identifies which
    chunks are candidates at all; see D-017 for why raw term-count coverage
    was replaced with IDF weighting).
  - semantic_score = raw cosine similarity (already 0..1-ish either way).
"""
from __future__ import annotations
import math
import sqlite3

from src.config import load_config
from src.module_b.retrieval.lexical import lexical_search
from src.module_b.retrieval.semantic import semantic_search
from src.module_b.retrieval.tokenize import tokenize


def _idf_weighted_overlap_scores(conn: sqlite3.Connection, query_text: str, chunk_ids: list[int],
                                  total_chunks: int) -> dict[int, float]:
    """Coverage of the query's IDF *mass* (not just its term count) that a
    chunk's title+heading+body actually contains. A plain term-count
    coverage ratio was tried first and rejected: boilerplate words that
    recur in nearly every chunk ("first-line", "management", "adult") then
    count exactly as much as a distinctive one ("dengue", "amlodipine",
    "migraine"), which both pulled irrelevant chunks to the top for
    on-topic queries and defeated abstention for off-corpus ones (a query
    made only of boilerplate words could still "cover" a chunk). IDF values
    are the same ones already computed for the offline TF-IDF semantic
    channel (stw_tfidf_vocab); a query term absent from the corpus entirely
    (e.g. "migraine") is treated as maximally rare (df=0 in the standard IDF
    formula) rather than ignored, so it drags the ratio down instead of
    being silently skipped when nothing in the corpus can match it."""
    query_terms = set(tokenize(query_text))
    if not query_terms or not chunk_ids:
        return {cid: 0.0 for cid in chunk_ids}
    idf = {r["term"]: r["idf"] for r in conn.execute("SELECT term, idf FROM stw_tfidf_vocab").fetchall()}
    default_idf = math.log(total_chunks + 1) + 1
    query_weight_total = sum(idf.get(t, default_idf) for t in query_terms)
    if query_weight_total == 0:
        return {cid: 0.0 for cid in chunk_ids}
    placeholders = ",".join("?" * len(chunk_ids))
    rows = conn.execute(
        f"""
        SELECT c.id, d.title, c.section_heading, c.chunk_text
        FROM stw_chunks c JOIN stw_documents d ON d.id = c.document_id
        WHERE c.id IN ({placeholders})
        """,
        chunk_ids,
    ).fetchall()
    scores = {}
    for r in rows:
        chunk_terms = set(tokenize(f"{r['title']} {r['section_heading']} {r['chunk_text']}"))
        matched_weight = sum(idf.get(t, default_idf) for t in (query_terms & chunk_terms))
        scores[r["id"]] = matched_weight / query_weight_total
    return scores


def _chunk_metadata(conn: sqlite3.Connection, chunk_ids: list[int]) -> dict[int, dict]:
    if not chunk_ids:
        return {}
    placeholders = ",".join("?" * len(chunk_ids))
    rows = conn.execute(
        f"""
        SELECT c.id AS chunk_id, c.section_heading, c.chunk_text, c.page,
               d.id AS document_id, d.doc_code, d.title, d.specialty, d.condition,
               d.source_type, d.version, d.effective_date, d.is_current, d.org
        FROM stw_chunks c JOIN stw_documents d ON d.id = c.document_id
        WHERE c.id IN ({placeholders})
        """,
        chunk_ids,
    ).fetchall()
    return {r["chunk_id"]: dict(r) for r in rows}


def hybrid_search(conn: sqlite3.Connection, query_text: str, top_k: int | None = None,
                   source_type_filter: str | None = None, include_superseded: bool = False) -> list[dict]:
    """Returns candidates sorted by combined score, each carrying full
    document/chunk metadata for citation and filtering downstream. Filters
    applied: is_current (unless include_superseded) and source_type (if
    given) -- both applied AFTER scoring against the metadata-unfiltered
    full corpus, so a filtered-out chunk never silently changes another
    chunk's relative ranking."""
    cfg = load_config()["retrieval"]
    top_k = top_k or cfg["top_k"]
    total_chunks = conn.execute("SELECT COUNT(*) c FROM stw_chunks").fetchone()["c"]
    pool_k = max(total_chunks, 1)  # corpus is small enough to score exhaustively rather than truncate a channel

    lexical_hits = lexical_search(conn, query_text, pool_k)
    semantic_hits = semantic_search(conn, query_text, pool_k)

    sem_scores = {h["chunk_id"]: h["cosine"] for h in semantic_hits}
    lexical_candidate_ids = [h["chunk_id"] for h in lexical_hits]
    lex_scores = _idf_weighted_overlap_scores(conn, query_text, lexical_candidate_ids, total_chunks)

    all_chunk_ids = sorted(set(lex_scores) | set(sem_scores))
    metadata = _chunk_metadata(conn, all_chunk_ids)

    w_lex, w_sem = cfg["hybrid_weight_lexical"], cfg["hybrid_weight_semantic"]
    candidates = []
    for chunk_id in all_chunk_ids:
        meta = metadata[chunk_id]
        if not include_superseded and not meta["is_current"]:
            continue
        if source_type_filter and meta["source_type"] != source_type_filter:
            continue
        lex_s, sem_s = lex_scores.get(chunk_id, 0.0), sem_scores.get(chunk_id, 0.0)
        combined = w_lex * lex_s + w_sem * sem_s
        candidates.append({**meta, "lexical_score": lex_s, "semantic_score": sem_s, "combined_score": combined})

    candidates.sort(key=lambda c: c["combined_score"], reverse=True)
    return candidates[:top_k]
