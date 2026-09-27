"""B.1 -- structural chunking of the 12 current STW PDFs plus the local
clinic protocol into clinically meaningful decision units.

Each STW one-pager is already pre-segmented by the source into named
sections (ASSESS, FIRST-LINE MANAGEMENT, RED FLAGS, DO NOT, REFER, ...).
Chunking here is a structural split on those printed headings (detected as
lines that are fully uppercase and not a bullet), never a blind token slice.
The local protocol's four numbered steps are the equivalent decision units
for that source.

Requires `pdftotext` (poppler-utils) on PATH -- a system dependency, not a
pip package; documented in README.md.

Idempotent: re-running against unchanged source files is a no-op (see
DESIGN.md D-006 / load_batch.find_completed_batch), keyed on the combined
content hash of every file in corpus/ plus the local protocol file.
"""
from __future__ import annotations
import hashlib
import re
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from src.config import load_config, REPO_ROOT, data_path
from src.module_a.ingest.load_batch import start_load_batch, finish_load_batch, find_completed_batch

SOURCE_NAME = "stw_corpus"

_SPECIALTY_BY_PREFIX = {
    "STW-GP": "General Practice",
    "STW-PED": "Pediatrics",
    "STW-GYN": "Gynecology & Obstetrics",
    "STW-ORT": "Orthopedics",
}

_CODE_RE = re.compile(r"Code:\s*(\S+)")
_VERSION_RE = re.compile(r"Version:\s*(\S+)")
_EFFECTIVE_RE = re.compile(r"Effective:\s*([\d-]+)")
_FOOTER_MARKERS = ("SYNTHETIC ASSESSMENT DOCUMENT", "ARCHIVE COPY")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_section_heading(line: str) -> bool:
    s = line.strip()
    if not s or s.startswith("•"):
        return False
    if any(marker in s for marker in _FOOTER_MARKERS):
        return False
    if "STANDARD TREATMENT WORKFLOW" in s or s.startswith("Code:"):
        return False
    # a heading line is fully uppercase once punctuation/spacing is ignored
    letters = re.sub(r"[^A-Za-z]", "", s)
    return bool(letters) and letters == letters.upper()


def parse_stw_pdf_text(text: str) -> dict:
    """Pure parse of pdftotext -layout output -> {doc_code, title, version,
    effective_date, chunks: [{section_heading, chunk_text, position}]}."""
    lines = text.split("\n")

    doc_code = version = effective_date = None
    title = None
    header_end_idx = 0
    for i, line in enumerate(lines[:6]):
        if (m := _CODE_RE.search(line)):
            doc_code = m.group(1)
        if (m := _VERSION_RE.search(line)):
            version = m.group(1)
        if (m := _EFFECTIVE_RE.search(line)):
            effective_date = m.group(1)
        if "STANDARD TREATMENT WORKFLOW" in line:
            header_end_idx = i
    # the title is the first non-blank line after the "STANDARD TREATMENT
    # WORKFLOW" label line, up to the first section heading
    for line in lines[header_end_idx + 1:]:
        if line.strip():
            title = line.strip()
            title = re.split(r"\s{2,}Supersedes:", title)[0].strip()
            break
    if doc_code is None or version is None or effective_date is None or title is None:
        raise ValueError(f"Could not parse required header fields from STW text (doc_code={doc_code}, "
                          f"version={version}, effective_date={effective_date}, title={title!r})")

    chunks = []
    current_heading, current_lines = None, []

    def _flush():
        if current_heading is not None:
            body = "\n".join(l.strip() for l in current_lines if l.strip())
            if body:
                chunks.append({"section_heading": current_heading, "chunk_text": body})

    for line in lines:
        if _is_section_heading(line):
            _flush()
            current_heading = line.strip()
            current_lines = []
        elif current_heading is not None:
            if any(marker in line for marker in _FOOTER_MARKERS):
                continue
            current_lines.append(line)
    _flush()

    for i, c in enumerate(chunks, start=1):
        c["position"] = i

    return {"doc_code": doc_code, "title": title, "version": version,
            "effective_date": effective_date, "chunks": chunks}


def parse_local_protocol(text: str) -> dict:
    """Pure parse of local_protocol_acute_fever.md's fixed structure into the
    same shape as parse_stw_pdf_text."""
    lines = text.splitlines()
    title = lines[0].lstrip("#").strip()

    meta_line = next(l for l in lines if l.strip().startswith("**Document:**"))
    doc_code = re.search(r"\*\*Document:\*\*\s*([^·*]+)", meta_line).group(1).strip()
    version = re.search(r"\*\*Version:\*\*\s*([^·*]+)", meta_line).group(1).strip()
    effective_date = re.search(r"\*\*Approved:\*\*\s*([^·*]+)", meta_line).group(1).strip()

    org = title.split("—")[0].strip() if "—" in title else title.split("-")[0].strip()

    numbered = re.compile(r"^\s*(\d+)\.\s+(.*)$")
    chunks = []
    for line in lines:
        m = numbered.match(line)
        if not m:
            continue
        position, body = int(m.group(1)), m.group(2).strip()
        body = body.replace("**", "")
        heading = body.split(":", 1)[0].strip()
        chunks.append({"section_heading": f"Step {position}: {heading}", "chunk_text": body, "position": position})

    return {"doc_code": doc_code, "title": title, "version": version,
            "effective_date": effective_date, "org": org, "chunks": chunks}


def _specialty_for_doc_code(doc_code: str) -> str | None:
    for prefix, specialty in _SPECIALTY_BY_PREFIX.items():
        if doc_code.startswith(prefix):
            return specialty
    return None


def _pdftotext(path: Path) -> str:
    try:
        result = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                                 capture_output=True, text=True, check=True)
    except FileNotFoundError as e:
        raise RuntimeError(
            "pdftotext (poppler-utils) is required to ingest the STW corpus and was not found on PATH. "
            "Install it (e.g. `apt-get install poppler-utils` / `brew install poppler`) and re-run."
        ) from e
    return result.stdout


def _combined_content_hash(pdf_paths: list[Path], protocol_path: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(pdf_paths) + [protocol_path]:
        with open(p, "rb") as f:
            h.update(f.read())
    return h.hexdigest()


def _insert_document(conn: sqlite3.Connection, batch_id: int, parsed: dict, source_type: str,
                      file_path: Path, raw_text: str) -> int:
    cur = conn.execute(
        """
        INSERT INTO stw_documents
            (doc_code, title, specialty, condition, source_type, version, effective_date,
             is_current, org, file_path, source, load_batch_id, raw_text, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
        """,
        (parsed["doc_code"], parsed["title"], _specialty_for_doc_code(parsed["doc_code"]) if source_type == "national_stw" else "Local Protocol",
         parsed["title"], source_type, parsed["version"], parsed["effective_date"],
         parsed.get("org"), str(file_path), SOURCE_NAME, batch_id, raw_text, _now()),
    )
    document_id = cur.lastrowid
    for c in parsed["chunks"]:
        conn.execute(
            "INSERT INTO stw_chunks (document_id, section_heading, chunk_text, position, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (document_id, c["section_heading"], c["chunk_text"], c["position"], _now()),
        )
        chunk_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        # The FTS index text is augmented with the document title and section
        # heading (not just the bullet body) -- a clinically meaningful chunk
        # is identified as much by *which document/condition* it's under as
        # by its own wording (e.g. "dengue" only ever appears in the document
        # title, never inside the "AVOID NSAIDs" bullet itself). This only
        # changes what is *searched*; stw_chunks.chunk_text (what is ever
        # quoted back to the user or checked for G6 verbatim-ness) is
        # untouched.
        fts_text = f"{parsed['title']} {c['section_heading']} {c['chunk_text']}"
        conn.execute("INSERT INTO stw_chunks_fts (rowid, chunk_text) VALUES (?, ?)", (chunk_id, fts_text))
    return document_id


def _recompute_is_current(conn: sqlite3.Connection) -> None:
    """Exactly one row per doc_code is current: the one with the latest
    effective_date. Same pattern as Module A's regulatory event-sourcing
    (D-009) -- never assume the ingestion order tells you which is current."""
    doc_codes = [r["doc_code"] for r in conn.execute("SELECT DISTINCT doc_code FROM stw_documents")]
    for code in doc_codes:
        rows = conn.execute(
            "SELECT id, effective_date FROM stw_documents WHERE doc_code=? ORDER BY effective_date", (code,)
        ).fetchall()
        latest_id = rows[-1]["id"]
        for r in rows:
            conn.execute("UPDATE stw_documents SET is_current=? WHERE id=?", (1 if r["id"] == latest_id else 0, r["id"]))


def load_stw_corpus(conn: sqlite3.Connection, corpus_dir: Path | None = None, protocol_path: Path | None = None) -> dict:
    corpus_dir = corpus_dir or (REPO_ROOT / load_config()["data_sources"]["corpus_dir"])
    protocol_path = protocol_path or data_path("local_protocol")

    pdf_paths = sorted(corpus_dir.glob("*.pdf"))
    if not pdf_paths:
        raise ValueError(f"No PDFs found in {corpus_dir}")

    file_hash = _combined_content_hash(pdf_paths, protocol_path)
    existing = find_completed_batch(conn, SOURCE_NAME, file_hash)
    if existing:
        docs = conn.execute("SELECT COUNT(*) c FROM stw_documents WHERE load_batch_id=?", (existing["id"],)).fetchone()["c"]
        chunks = conn.execute(
            "SELECT COUNT(*) c FROM stw_chunks WHERE document_id IN (SELECT id FROM stw_documents WHERE load_batch_id=?)",
            (existing["id"],),
        ).fetchone()["c"]
        return {"batch_id": existing["id"], "documents": docs, "chunks": chunks, "skipped": True}

    batch_id = start_load_batch(conn, SOURCE_NAME, None, str(corpus_dir), file_hash)

    n_docs, n_chunks = 0, 0
    for pdf_path in pdf_paths:
        raw_text = _pdftotext(pdf_path)
        parsed = parse_stw_pdf_text(raw_text)
        _insert_document(conn, batch_id, parsed, "national_stw", pdf_path, raw_text)
        n_docs += 1
        n_chunks += len(parsed["chunks"])

    protocol_text = protocol_path.read_text()
    parsed_protocol = parse_local_protocol(protocol_text)
    _insert_document(conn, batch_id, parsed_protocol, "local_protocol", protocol_path, protocol_text)
    n_docs += 1
    n_chunks += len(parsed_protocol["chunks"])

    _recompute_is_current(conn)
    conn.commit()
    finish_load_batch(conn, batch_id, row_count=n_docs, notes=f"{n_docs} documents, {n_chunks} chunks")
    return {"batch_id": batch_id, "documents": n_docs, "chunks": n_chunks, "skipped": False}
