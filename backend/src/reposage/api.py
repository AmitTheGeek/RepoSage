"""FastAPI application for RepoSage retrieval."""

from __future__ import annotations

import logging
import os
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from reposage.answering import (
    AnswerProvider,
    AnswerProviderFailure,
    AnswerProviderNotConfigured,
    AnswerProviderQuotaError,
    AnswerProviderTimeout,
    AnswerResult,
    DEFAULT_GEMINI_MODEL,
    InvalidAnswerResponse,
    generate_grounded_answer,
    gemini_provider_from_environment,
)
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


class AnswerSourceResponse(BaseModel):
    source_id: str
    chunk_id: str
    path: str
    start_line: int
    end_line: int
    text: str
    score: float
    citation: str


class AnswerClaimResponse(BaseModel):
    text: str
    source_ids: list[str]
    citations: list[str]


class AnswerResponse(BaseModel):
    query: str
    status: str
    model_id: str
    index_metadata: IndexMetadataResponse
    score_direction: str
    claims: list[AnswerClaimResponse]
    sources: list[AnswerSourceResponse]
    usage: dict[str, Any] | None = None
    latency_ms: int | None = None


def create_app(
    *,
    answer_provider_factory: Callable[[], AnswerProvider] | None = None,
) -> FastAPI:
    provider_factory = answer_provider_factory or gemini_provider_from_environment
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
        query = _validated_query(request.query)

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

    @app.post("/answer", response_model=AnswerResponse)
    def answer_endpoint(request: SearchRequest) -> AnswerResponse:
        query = _validated_query(request.query)

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
            LOGGER.exception("Unexpected RepoSage search failure before answer generation")
            raise HTTPException(
                status_code=500,
                detail="RepoSage answer retrieval failed unexpectedly.",
            ) from exc

        if not results:
            answer = AnswerResult(
                status="insufficient_evidence",
                claims=(),
                sources=(),
                model_id=_configured_answer_model_id(),
            )
            return _answer_response(query=query, metadata=metadata, answer=answer)

        try:
            provider = provider_factory()
            answer = generate_grounded_answer(
                query=query,
                search_results=results,
                provider=provider,
            )
        except AnswerProviderNotConfigured as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "gemini_not_configured",
                    "message": (
                        "Gemini answering is not configured. Set GEMINI_API_KEY "
                        "on the server before calling /answer."
                    ),
                },
            ) from exc
        except AnswerProviderQuotaError as exc:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "gemini_quota_or_rate_limited",
                    "message": "Gemini quota or rate limit was reached. Try again later.",
                },
            ) from exc
        except AnswerProviderTimeout as exc:
            raise HTTPException(
                status_code=504,
                detail={
                    "code": "gemini_timeout",
                    "message": "Gemini did not return an answer before the server timeout.",
                },
            ) from exc
        except InvalidAnswerResponse as exc:
            LOGGER.warning("Gemini returned invalid structured answer output: %s", exc)
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "gemini_invalid_response",
                    "message": (
                        "Gemini returned an answer whose structure or source references "
                        "could not be validated."
                    ),
                },
            ) from exc
        except AnswerProviderFailure as exc:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "gemini_provider_failure",
                    "message": "Gemini answer generation failed.",
                },
            ) from exc

        return _answer_response(query=query, metadata=metadata, answer=answer)

    return app


def _validated_query(raw_query: str) -> str:
    query = raw_query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="query must not be blank")
    if len(query) > MAX_QUERY_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"query must be {MAX_QUERY_LENGTH} characters or fewer",
        )
    return query


def _answer_response(
    *,
    query: str,
    metadata: IndexMetadataResponse,
    answer: AnswerResult,
) -> AnswerResponse:
    return AnswerResponse(
        query=query,
        status=answer.status,
        model_id=answer.model_id,
        index_metadata=metadata,
        score_direction=SCORE_DIRECTION,
        claims=[
            AnswerClaimResponse(
                text=claim.text,
                source_ids=list(claim.source_ids),
                citations=list(claim.citations),
            )
            for claim in answer.claims
        ],
        sources=[
            AnswerSourceResponse(**asdict(source))
            for source in answer.sources
        ],
        usage=answer.usage,
        latency_ms=answer.latency_ms,
    )


def _configured_db_path() -> Path:
    raw_path = os.environ.get("REPOSAGE_DB_PATH")
    if raw_path is None or not raw_path.strip():
        raise _IndexUnavailable
    return Path(raw_path)


def _configured_answer_model_id() -> str:
    return os.environ.get("REPOSAGE_GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL


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
