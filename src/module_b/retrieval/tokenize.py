"""Shared tokenizer for both retrieval channels (lexical overlap scoring and
the offline TF-IDF semantic backend), so "does this query term appear in
this chunk" means the same thing in both places."""
from __future__ import annotations
import re

STOPWORDS = {"a", "an", "the", "and", "or", "of", "in", "to", "for", "with", "per",
             "is", "are", "at", "on", "as", "this", "that", "be", "if", "no", "not",
             "what", "which", "does", "do", "when", "why"}


def _stem(term: str) -> str:
    """Deliberately crude suffix-stripping (not a real Porter stemmer) so
    obvious word-form variants line up between a question and the source
    text -- e.g. "avoided"/"avoid", "antibiotics"/"antibiotic" -- without
    pulling in a stemming dependency. Guarded to avoid the common
    over-stripping mistakes (double letters, very short results)."""
    if len(term) > 5 and term.endswith("ing"):
        term = term[:-3]
    elif len(term) > 4 and term.endswith("ied"):
        term = term[:-3] + "y"
    elif len(term) > 4 and term.endswith("ed") and not term.endswith("eed"):
        term = term[:-2]
    if len(term) > 4 and term.endswith("ies"):
        term = term[:-3] + "y"
    elif len(term) > 3 and term.endswith("es") and term[-3] in "sxz":
        term = term[:-2]
    elif len(term) > 3 and term.endswith("s") and not term.endswith("ss"):
        term = term[:-1]
    return term


def tokenize(text: str) -> list[str]:
    return [_stem(t) for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) >= 2 and t not in STOPWORDS]
