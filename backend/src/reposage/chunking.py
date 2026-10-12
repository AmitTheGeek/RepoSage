"""Deterministic line-based chunking."""

from __future__ import annotations

import hashlib

from reposage.models import Chunk, IngestedFile


def split_file_into_chunks(
    source_file: IngestedFile,
    *,
    git_head: str | None,
    git_dirty: bool,
    indexed_at_utc: str,
    chunk_lines: int = 80,
    overlap_lines: int = 15,
) -> list[Chunk]:
    if chunk_lines <= 0:
        raise ValueError("chunk_lines must be positive")
    if overlap_lines < 0:
        raise ValueError("overlap_lines cannot be negative")
    if overlap_lines >= chunk_lines:
        raise ValueError("overlap_lines must be smaller than chunk_lines")

    lines = source_file.text.splitlines(keepends=True)
    if not lines:
        return []

    chunks: list[Chunk] = []
    step = chunk_lines - overlap_lines
    start_index = 0
    while start_index < len(lines):
        end_index = min(start_index + chunk_lines, len(lines))
        start_line = start_index + 1
        end_line = end_index
        text = "".join(lines[start_index:end_index])
        chunk_id = _chunk_id(
            source_file.path,
            source_file.content_hash,
            start_line,
            end_line,
        )
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                path=source_file.path,
                start_line=start_line,
                end_line=end_line,
                text=text,
                file_hash=source_file.content_hash,
                git_head=git_head,
                git_dirty=git_dirty,
                indexed_at_utc=indexed_at_utc,
            ),
        )
        if end_index == len(lines):
            break
        start_index += step
    return chunks


def _chunk_id(path: str, file_hash: str, start_line: int, end_line: int) -> str:
    payload = f"{path}\0{file_hash}\0{start_line}\0{end_line}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]
