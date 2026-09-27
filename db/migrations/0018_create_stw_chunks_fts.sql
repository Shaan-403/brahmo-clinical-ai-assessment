-- Lexical retrieval channel. Populated explicitly by the loader alongside
-- stw_chunks (no triggers) -- consistent with this codebase's style of
-- explicit writes rather than implicit DB magic.
CREATE VIRTUAL TABLE stw_chunks_fts USING fts5(chunk_text, content='stw_chunks', content_rowid='id');
