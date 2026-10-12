"""Repository indexing orchestration."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from reposage.chunking import split_file_into_chunks
from reposage.ingestion import ingest_repository
from reposage.models import Chunk, IndexReport
from reposage.storage import rebuild_database


def index_repository(
    repo_path: str | Path,
    db_path: str | Path,
    *,
    chunk_lines: int = 80,
    overlap_lines: int = 15,
) -> IndexReport:
    indexed_at_utc = datetime.now(UTC).isoformat(timespec="seconds")
    ingestion = ingest_repository(repo_path)

    chunks: list[Chunk] = []
    for source_file in ingestion.files:
        chunks.extend(
            split_file_into_chunks(
                source_file,
                git_head=ingestion.git_metadata.head,
                git_dirty=ingestion.git_metadata.dirty,
                indexed_at_utc=indexed_at_utc,
                chunk_lines=chunk_lines,
                overlap_lines=overlap_lines,
            ),
        )

    report = IndexReport(
        repo_root=str(ingestion.repo_root),
        db_path=str(Path(db_path)),
        git_head=ingestion.git_metadata.head,
        git_dirty=ingestion.git_metadata.dirty,
        indexed_at_utc=indexed_at_utc,
        chunk_lines=chunk_lines,
        overlap_lines=overlap_lines,
        files_indexed=len(ingestion.files),
        chunks_indexed=len(chunks),
        skipped_files=ingestion.skipped_files,
    )

    metadata = {
        key: _metadata_value(value)
        for key, value in asdict(report).items()
        if key != "skipped_files"
    }
    rebuild_database(
        db_path,
        chunks=chunks,
        metadata=metadata,
        skipped_files=ingestion.skipped_files,
    )
    return report


def _metadata_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
