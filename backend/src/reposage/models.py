"""Shared value objects for indexing and retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SkippedFile:
    path: str
    reason: str


@dataclass(frozen=True)
class IngestedFile:
    path: str
    absolute_path: Path
    text: str
    content_hash: str
    line_count: int


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    path: str
    start_line: int
    end_line: int
    text: str
    file_hash: str
    git_head: str | None
    git_dirty: bool
    indexed_at_utc: str

    @property
    def citation(self) -> str:
        return f"{self.path}:L{self.start_line}-L{self.end_line}"


@dataclass(frozen=True)
class IndexReport:
    repo_root: str
    db_path: str
    git_head: str | None
    git_dirty: bool
    indexed_at_utc: str
    chunk_lines: int
    overlap_lines: int
    files_indexed: int
    chunks_indexed: int
    skipped_files: list[SkippedFile] = field(default_factory=list)


@dataclass(frozen=True)
class SearchResult:
    chunk_id: str
    path: str
    start_line: int
    end_line: int
    text: str
    score: float
    citation: str
