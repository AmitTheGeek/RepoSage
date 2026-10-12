"""Safe query handling and retrieval."""

from __future__ import annotations

from pathlib import Path

from reposage.errors import BlankQueryError
from reposage.models import SearchResult
from reposage.normalize import normalize_query_terms
from reposage.storage import search_database


def search(db_path: str | Path, query: str, top_k: int = 5) -> list[SearchResult]:
    fts_query = safe_fts_query(query)
    return search_database(db_path, fts_query=fts_query, top_k=top_k)


def safe_fts_query(query: str) -> str:
    terms = normalize_query_terms(query)
    if not terms:
        raise BlankQueryError("query is blank or contains no searchable terms")
    return " OR ".join(_quote_fts_term(term) for term in terms)


def _quote_fts_term(term: str) -> str:
    escaped = term.replace('"', '""')
    return f'"{escaped}"'
