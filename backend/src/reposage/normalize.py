"""Identifier-aware text normalization for FTS indexing and querying."""

from __future__ import annotations

import re
from collections.abc import Iterable

IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
WORD_RE = re.compile(r"[A-Za-z0-9_]+")
CAMEL_PART_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+")

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "do",
    "does",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}


def split_identifier(identifier: str) -> list[str]:
    """Split camelCase, PascalCase, snake_case, and digit runs."""
    parts: list[str] = []
    for snake_part in re.split(r"_+", identifier):
        if not snake_part:
            continue
        camel_parts = CAMEL_PART_RE.findall(snake_part)
        parts.extend(camel_parts or [snake_part])
    return parts


def normalize_searchable_text(path: str, source_text: str) -> str:
    """Return text for FTS while keeping source text unchanged elsewhere."""
    expanded_terms: list[str] = []
    path_tokens = WORD_RE.findall(path.replace("/", " ").replace(".", " "))
    for token in path_tokens:
        expanded_terms.append(token)
        expanded_terms.extend(split_identifier(token) * 2)

    for match in IDENTIFIER_RE.finditer(source_text):
        identifier = match.group(0)
        expanded_terms.append(identifier)
        expanded_terms.extend(split_identifier(identifier) * 4)

    return "\n".join(
        [
            path,
            source_text,
            " ".join(expanded_terms),
        ],
    )


def normalize_query_terms(query: str, max_terms: int = 40) -> list[str]:
    """Convert ordinary question text into safe, deterministic FTS terms."""
    terms: list[str] = []
    for raw_token in WORD_RE.findall(query):
        candidates = [raw_token, *split_identifier(raw_token)]
        for candidate in candidates:
            for variant in _term_variants(candidate.lower()):
                if _is_searchable_query_term(variant):
                    terms.append(variant)
    return _dedupe(terms)[:max_terms]


def _is_searchable_query_term(term: str) -> bool:
    return len(term) >= 2 and term not in STOPWORDS


def _term_variants(term: str) -> Iterable[str]:
    yield term

    if len(term) > 4 and term.endswith("ies"):
        yield f"{term[:-3]}y"

    if len(term) > 4 and term.endswith("ed"):
        yield term[:-1]
        yield term[:-2]

    if len(term) > 5 and term.endswith("ing"):
        base = term[:-3]
        yield base
        yield f"{base}e"

    if len(term) > 3 and term.endswith("s"):
        yield term[:-1]


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped
