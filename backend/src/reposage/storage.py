"""SQLite persistence for chunks and FTS5/BM25 retrieval."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from reposage.errors import Fts5UnavailableError, MissingIndexError
from reposage.models import Chunk, SearchResult, SkippedFile
from reposage.normalize import normalize_searchable_text

SCHEMA_VERSION = "1"
SCORE_DIRECTION = (
    "lower scores rank higher; scores are adjusted SQLite FTS5 BM25 ranking "
    "values, not confidence"
)


def rebuild_database(
    db_path: str | Path,
    *,
    chunks: list[Chunk],
    metadata: dict[str, str],
    skipped_files: list[SkippedFile],
) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(path) as conn:
        check_fts5(conn)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(
            """
            DROP TABLE IF EXISTS chunks_fts;
            DROP TABLE IF EXISTS chunks;
            DROP TABLE IF EXISTS skipped_files;
            DROP TABLE IF EXISTS index_metadata;

            CREATE TABLE index_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE skipped_files (
                path TEXT PRIMARY KEY,
                reason TEXT NOT NULL
            );

            CREATE TABLE chunks (
                id INTEGER PRIMARY KEY,
                chunk_id TEXT NOT NULL UNIQUE,
                path TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                text TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                git_head TEXT,
                git_dirty INTEGER NOT NULL,
                indexed_at_utc TEXT NOT NULL
            );

            CREATE VIRTUAL TABLE chunks_fts USING fts5(
                path,
                searchable_text,
                content=''
            );
            """,
        )

        stored_metadata = {"schema_version": SCHEMA_VERSION, **metadata}
        conn.executemany(
            "INSERT INTO index_metadata(key, value) VALUES (?, ?)",
            sorted(stored_metadata.items()),
        )
        conn.executemany(
            "INSERT INTO skipped_files(path, reason) VALUES (?, ?)",
            [(skipped.path, skipped.reason) for skipped in skipped_files],
        )

        for chunk in sorted(chunks, key=lambda item: (item.path, item.start_line)):
            cursor = conn.execute(
                """
                INSERT INTO chunks(
                    chunk_id,
                    path,
                    start_line,
                    end_line,
                    text,
                    file_hash,
                    git_head,
                    git_dirty,
                    indexed_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.chunk_id,
                    chunk.path,
                    chunk.start_line,
                    chunk.end_line,
                    chunk.text,
                    chunk.file_hash,
                    chunk.git_head,
                    int(chunk.git_dirty),
                    chunk.indexed_at_utc,
                ),
            )
            rowid = cursor.lastrowid
            searchable_text = normalize_searchable_text(chunk.path, chunk.text)
            conn.execute(
                """
                INSERT INTO chunks_fts(rowid, path, searchable_text)
                VALUES (?, ?, ?)
                """,
                (rowid, chunk.path, searchable_text),
            )


def check_fts5(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("CREATE VIRTUAL TABLE temp.reposage_fts5_probe USING fts5(value)")
        conn.execute("DROP TABLE temp.reposage_fts5_probe")
    except sqlite3.OperationalError as exc:
        raise Fts5UnavailableError(
            "SQLite FTS5 is unavailable in this Python build. "
            "Install or use a Python distribution whose sqlite3 module was built "
            "with ENABLE_FTS5, then rebuild the RepoSage index.",
        ) from exc


def search_database(
    db_path: str | Path,
    *,
    fts_query: str,
    top_k: int,
) -> list[SearchResult]:
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    path = Path(db_path)
    if not path.exists():
        raise MissingIndexError(f"index database does not exist: {path}")

    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        _ensure_index(conn, path)
        rows = conn.execute(
            """
            WITH ranked AS (
                SELECT
                    c.chunk_id,
                    c.path,
                    c.start_line,
                    c.end_line,
                    c.text,
                    bm25(chunks_fts, 1.5, 1.0) +
                        CASE
                            WHEN lower(c.path) LIKE '%.md' THEN 20.0
                            ELSE 0.0
                        END AS score
                FROM chunks_fts
                JOIN chunks AS c ON c.id = chunks_fts.rowid
                WHERE chunks_fts MATCH ?
            )
            SELECT chunk_id, path, start_line, end_line, text, score
            FROM ranked
            ORDER BY score ASC, path ASC, start_line ASC, chunk_id ASC
            LIMIT ?
            """,
            (fts_query, top_k),
        ).fetchall()

    return [
        SearchResult(
            chunk_id=row["chunk_id"],
            path=row["path"],
            start_line=row["start_line"],
            end_line=row["end_line"],
            text=row["text"],
            score=float(row["score"]),
            citation=f"{row['path']}:L{row['start_line']}-L{row['end_line']}",
        )
        for row in rows
    ]


def read_metadata(db_path: str | Path) -> dict[str, str]:
    path = Path(db_path)
    if not path.exists():
        raise MissingIndexError(f"index database does not exist: {path}")
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        _ensure_index(conn, path)
        rows = conn.execute("SELECT key, value FROM index_metadata").fetchall()
    return {row["key"]: row["value"] for row in rows}


def _ensure_index(conn: sqlite3.Connection, path: Path) -> None:
    table_names = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')",
        )
    }
    required = {"index_metadata", "chunks", "chunks_fts"}
    missing = required - table_names
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise MissingIndexError(
            f"{path} is not a RepoSage index; missing table(s): {missing_list}",
        )
