"""B.3 -- grounded answering, deterministic and retrieval-only.

Deliberately NOT an LLM-generation step: the "answer" is the retrieved
chunk text itself, verbatim, wrapped in a fixed citation template. Given
"no external clinical knowledge should be used" and the brief's own bars
(never fabricate a citation, never calculate a dose, never synthesize a
third recommendation from a conflict), a system that can only ever emit
text it retrieved cannot fabricate a citation or invent a number by
construction -- see DESIGN.md D-018.

Answer states:
  ANSWERED  -- one or more chunks from a single source_type, all above the
              minimum score, cleared for citation.
  PARTIAL   -- a comparison was requested/implied (both source_types
              present among the candidates) but only one side actually has
              a matching chunk in this corpus; the present side is answered,
              the missing side is named explicitly as missing, never
              silently dropped.
  ABSTAINED -- nothing in the corpus clears the minimum score at all.

A genuine two-sided comparison (both local_protocol and national_stw both
clear the floor for the same question) returns BOTH as separate, individually
cited blocks -- never merged into a single synthesized recommendation.
"""
from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone

from src.config import load_config
from src.module_b.retrieval.hybrid import hybrid_search

_SOURCE_TYPES = ("national_stw", "local_protocol")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _citation(c: dict) -> dict:
    return {
        "doc_code": c["doc_code"], "title": c["title"], "version": c["version"],
        "effective_date": c["effective_date"], "source_type": c["source_type"],
        "org": c["org"], "section_heading": c["section_heading"],
        "is_current": bool(c["is_current"]),
    }


def _block(candidates_for_doc: list[dict], source_type: str) -> dict:
    label = ("clinic's own protocol -- not national guidance" if source_type == "local_protocol"
             else "national workflow")
    return {
        "source_type": source_type, "label": label,
        "statements": [{"text": c["chunk_text"], "citation": _citation(c), "score": round(c["combined_score"], 4)}
                       for c in candidates_for_doc],
    }


def _best_document_group(candidates: list[dict], floor: float, ratio: float) -> list[dict]:
    """Given candidates already filtered to one source_type and sorted by
    score, returns the supporting set: the best-scoring document's chunks
    that clear the ratio-of-best bar, gated on that TOP chunk alone first
    clearing the absolute floor -- so a document with no genuinely strong
    match never qualifies at all (that's what makes abstention work), but a
    second, differently-worded bullet from the SAME document (already
    proven relevant by its top chunk) isn't held to that same absolute bar
    a second time. A within-document ranking tie/near-tie between two
    decision-unit chunks (e.g. a "SUSPECT" bullet edging out the "AVOID"
    bullet that actually answers the question) is common with a keyword/
    TF-IDF retriever with no true synonym understanding; requiring every
    supporting chunk to independently re-clear the absolute floor punished
    exactly this case by dropping the correct chunk. See DESIGN.md D-017."""
    if not candidates:
        return []
    top = candidates[0]
    if top["combined_score"] < floor:
        return []
    top_document_id = top["document_id"]
    best_score = top["combined_score"]
    return [c for c in candidates if c["document_id"] == top_document_id
            and c["combined_score"] >= best_score * ratio]


def answer_question(conn: sqlite3.Connection, question_text: str, source_type_filter: str | None = None,
                     include_superseded: bool = False, persist: bool = True) -> dict:
    cfg = load_config()["retrieval"]
    floor, ratio = cfg["min_combined_score_to_answer"], cfg["supporting_citation_score_ratio"]

    candidates = hybrid_search(conn, question_text, source_type_filter=source_type_filter,
                                include_superseded=include_superseded)

    by_source_type = {st: [c for c in candidates if c["source_type"] == st] for st in _SOURCE_TYPES}
    groups = {st: _best_document_group(cands, floor, ratio) for st, cands in by_source_type.items()}
    present_types = [st for st, g in groups.items() if g]

    result: dict = {"question": question_text, "retrieval_method": None, "filters_applied": {
        "source_type_filter": source_type_filter, "include_superseded": include_superseded}}

    if not present_types:
        result.update({
            "state": "ABSTAINED",
            "answer": None,
            "abstention_reason": "No document in this corpus (STW pack or local protocol) scores above the "
                                  "minimum confidence threshold for this question -- nothing here supports "
                                  "an answer.",
        })
    elif source_type_filter is None and "local_protocol" in present_types:
        # The local protocol only covers one condition (acute undifferentiated
        # fever). Whenever it matches at all with no explicit filter, this is
        # inherently the "local vs. national" comparison case the brief
        # requires -- always check and report the national side too, present
        # or absent, rather than silently answering only from local content.
        result.update({
            "state": "ANSWERED" if "national_stw" in present_types else "PARTIAL",
            "answer": {st: _block(groups[st], st) for st in present_types},
            "note": "The clinic's local protocol matched this question -- the national workflow pack was "
                    "checked separately and is shown alongside it, never merged into one recommendation.",
        })
        if "national_stw" not in present_types:
            result["abstention_reason"] = ("No matching national STW document was found for this question -- "
                                            "only the clinic's own local protocol addresses it in this corpus.")
    else:
        st = present_types[0]
        result.update({"state": "ANSWERED", "answer": {st: _block(groups[st], st)}})

    # provenance: which chunks were actually retrieved/considered, not just cited
    result["candidates_considered"] = [
        {"chunk_id": c["chunk_id"], "doc_code": c["doc_code"], "source_type": c["source_type"],
         "combined_score": round(c["combined_score"], 4)}
        for c in candidates
    ]
    row = conn.execute("SELECT DISTINCT method FROM stw_chunk_embeddings").fetchone()
    result["retrieval_method"] = f"hybrid(fts5_bm25 + {row['method'] if row else 'none'})"

    if persist:
        cur = conn.execute(
            """
            INSERT INTO rag_answers (question, state, answer_json, abstention_reason, retrieval_method,
                                      filters_applied_json, evaluated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (question_text, result["state"], json.dumps(result.get("answer")), result.get("abstention_reason"),
             result["retrieval_method"], json.dumps(result["filters_applied"]), _now()),
        )
        conn.commit()
        result["id"] = cur.lastrowid

    return result
