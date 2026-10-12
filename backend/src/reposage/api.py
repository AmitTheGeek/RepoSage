"""FastAPI application for RepoSage retrieval."""

from __future__ import annotations

import logging
import os
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from reposage.errors import BlankQueryError, Fts5UnavailableError, MissingIndexError
from reposage.retrieval import search
from reposage.storage import SCORE_DIRECTION, read_metadata

LOGGER = logging.getLogger(__name__)
MAX_QUERY_LENGTH = 2_000
INDEX_UNAVAILABLE_MESSAGE = (
    "RepoSage index is unavailable. Build an index with `reposage index` and set "
    "REPOSAGE_DB_PATH to the SQLite database before searching."
)

SAFE_METADATA_KEYS = {
    "schema_version",
    "git_head",
    "git_dirty",
    "indexed_at_utc",
    "chunk_lines",
    "overlap_lines",
    "files_indexed",
    "chunks_indexed",
}


class SearchRequest(BaseModel):
    query: str = Field(..., max_length=MAX_QUERY_LENGTH)
    top_k: int = Field(default=5, ge=1, le=20)


class IndexMetadataResponse(BaseModel):
    git_dirty: bool
    files_indexed: int
    chunks_indexed: int
    git_head: str
    schema_version: str | None = None
    indexed_at_utc: str | None = None
    chunk_lines: int | None = None
    overlap_lines: int | None = None


class SearchResultResponse(BaseModel):
    chunk_id: str
    path: str
    start_line: int
    end_line: int
    text: str
    score: float
    citation: str


class SearchResponse(BaseModel):
    query: str
    index_metadata: IndexMetadataResponse
    score_direction: str
    results: list[SearchResultResponse]


def create_app() -> FastAPI:
    app = FastAPI(title="RepoSage Retrieval API", version="0.2.0")

    @app.get("/health")
    def health() -> dict[str, Any]:
        try:
            metadata = _load_safe_metadata()
        except _IndexUnavailable:
            return {
                "status": "degraded",
                "index_ready": False,
                "message": INDEX_UNAVAILABLE_MESSAGE,
            }

        return {
            "status": "ok",
            "index_ready": True,
            "index_metadata": metadata,
        }

    @app.post("/search", response_model=SearchResponse)
    def search_endpoint(request: SearchRequest) -> SearchResponse:
        query = request.query.strip()
        if not query:
            raise HTTPException(status_code=422, detail="query must not be blank")
        if len(query) > MAX_QUERY_LENGTH:
            raise HTTPException(
                status_code=422,
                detail=f"query must be {MAX_QUERY_LENGTH} characters or fewer",
            )

        try:
            db_path = _configured_db_path()
            metadata = _load_safe_metadata(db_path)
            results = search(db_path, query, top_k=request.top_k)
        except BlankQueryError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except _IndexUnavailable as exc:
            raise HTTPException(
                status_code=503,
                detail=INDEX_UNAVAILABLE_MESSAGE,
            ) from exc
        except (MissingIndexError, Fts5UnavailableError, sqlite3.Error) as exc:
            LOGGER.warning("RepoSage index is unavailable: %s", exc)
            raise HTTPException(
                status_code=503,
                detail=INDEX_UNAVAILABLE_MESSAGE,
            ) from exc
        except Exception as exc:  # pragma: no cover - defensive API boundary.
            LOGGER.exception("Unexpected RepoSage API failure")
            raise HTTPException(
                status_code=500,
                detail="RepoSage search failed unexpectedly.",
            ) from exc

        return SearchResponse(
            query=query,
            index_metadata=metadata,
            score_direction=SCORE_DIRECTION,
            results=[
                SearchResultResponse(**asdict(result))
                for result in results
            ],
        )

    return app


def _configured_db_path() -> Path:
    raw_path = os.environ.get("REPOSAGE_DB_PATH")
    if raw_path is None or not raw_path.strip():
        raise _IndexUnavailable
    return Path(raw_path)


def _load_safe_metadata(db_path: Path | None = None) -> IndexMetadataResponse:
    try:
        metadata = read_metadata(db_path or _configured_db_path())
    except (MissingIndexError, Fts5UnavailableError, sqlite3.Error) as exc:
        LOGGER.info("RepoSage index metadata unavailable: %s", exc)
        raise _IndexUnavailable from exc
    return _safe_metadata_response(metadata)


def _safe_metadata_response(metadata: dict[str, str]) -> IndexMetadataResponse:
    safe_metadata = {
        key: value
        for key, value in metadata.items()
        if key in SAFE_METADATA_KEYS
    }
    return IndexMetadataResponse(
        git_dirty=_parse_bool(safe_metadata.get("git_dirty", "false")),
        files_indexed=_parse_int(safe_metadata.get("files_indexed", "0")),
        chunks_indexed=_parse_int(safe_metadata.get("chunks_indexed", "0")),
        git_head=safe_metadata.get("git_head", ""),
        schema_version=safe_metadata.get("schema_version") or None,
        indexed_at_utc=safe_metadata.get("indexed_at_utc") or None,
        chunk_lines=_parse_optional_int(safe_metadata.get("chunk_lines")),
        overlap_lines=_parse_optional_int(safe_metadata.get("overlap_lines")),
    )


def _parse_bool(value: str) -> bool:
    return value.lower() == "true"


def _parse_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def _parse_optional_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return _parse_int(value)


class _IndexUnavailable(Exception):
    """Internal signal for safe 503/health responses."""


app = create_app()
