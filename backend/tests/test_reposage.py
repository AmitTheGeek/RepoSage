from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = BACKEND_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from reposage.chunking import split_file_into_chunks
from reposage.errors import BlankQueryError, MissingIndexError
from reposage.indexing import index_repository
from reposage.models import IngestedFile
from reposage.retrieval import search


class ChunkingTests(unittest.TestCase):
    def test_line_boundaries_and_overlap_are_deterministic(self) -> None:
        text = "".join(f"line {number}\n" for number in range(1, 13))
        source_file = IngestedFile(
            path="src/Example.kt",
            absolute_path=Path("src/Example.kt"),
            text=text,
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            line_count=12,
        )

        chunks = split_file_into_chunks(
            source_file,
            git_head="abc123",
            git_dirty=False,
            indexed_at_utc="2026-10-10T00:00:00+00:00",
            chunk_lines=5,
            overlap_lines=2,
        )

        self.assertEqual(
            [(chunk.start_line, chunk.end_line) for chunk in chunks],
            [(1, 5), (4, 8), (7, 11), (10, 12)],
        )
        self.assertEqual(chunks[1].text, "line 4\nline 5\nline 6\nline 7\nline 8\n")
        self.assertEqual(chunks[-1].citation, "src/Example.kt:L10-L12")


@unittest.skipIf(shutil.which("git") is None, "git is required for ingestion tests")
class IndexAndSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        _git(self.repo, "init")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_exact_citations_identifier_matching_safe_querying_and_persistence(self) -> None:
        source = (
            "package sample\n"
            "\n"
            "class CacheStore {\n"
            "    fun cacheFreshnessChecker() {\n"
            "        val searchData = \"cached\"\n"
            "    }\n"
            "}\n"
        )
        _write(self.repo / "src/CacheStore.kt", source)
        _write(self.repo / "notes.txt", "unsupported but tracked\n")
        _git(self.repo, "add", ".")

        db_path = self.root / "reposage.db"
        report = index_repository(self.repo, db_path, chunk_lines=80, overlap_lines=15)
        self.assertEqual(report.files_indexed, 1)
        self.assertEqual(report.chunks_indexed, 1)
        self.assertIn("unsupported extension", {item.reason for item in report.skipped_files})

        results = search(db_path, "cache freshness checker", top_k=3)
        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result.path, "src/CacheStore.kt")
        self.assertEqual(result.citation, "src/CacheStore.kt:L1-L7")
        self.assertEqual(result.text, source)

        no_matches = search(db_path, "no such symbol anywhere", top_k=3)
        self.assertEqual(no_matches, [])

        injected = search(db_path, "'); DROP TABLE chunks; --", top_k=3)
        self.assertEqual(injected, [])
        self.assertEqual(search(db_path, "search data", top_k=1)[0].path, "src/CacheStore.kt")

        with self.assertRaises(BlankQueryError):
            search(db_path, "   \n\t", top_k=3)
        with self.assertRaises(MissingIndexError):
            search(self.root / "missing.db", "cache", top_k=3)

        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC_ROOT)
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "reposage.cli",
                "search",
                "--db",
                str(db_path),
                "--query",
                "cache freshness checker",
                "--top-k",
                "1",
                "--json",
            ],
            check=True,
            text=True,
            capture_output=True,
            env=env,
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["results"][0]["citation"], "src/CacheStore.kt:L1-L7")

    def test_reindex_reflects_edits_and_deletions_without_duplicates(self) -> None:
        _write(
            self.repo / "src/One.kt",
            "package sample\n\nfun legacyonlymarker() = Unit\n",
        )
        _write(
            self.repo / "src/Two.kt",
            "package sample\n\nfun deletedonlymarker() = Unit\n",
        )
        _git(self.repo, "add", ".")

        db_path = self.root / "reposage.db"
        index_repository(self.repo, db_path)
        self.assertEqual(search(db_path, "legacyonlymarker", top_k=10)[0].path, "src/One.kt")
        self.assertEqual(search(db_path, "deletedonlymarker", top_k=10)[0].path, "src/Two.kt")

        _write(
            self.repo / "src/One.kt",
            "package sample\n\nfun modernonlymarker() = Unit\n",
        )
        (self.repo / "src/Two.kt").unlink()

        report = index_repository(self.repo, db_path)
        self.assertEqual(report.files_indexed, 1)
        self.assertEqual(report.chunks_indexed, 1)
        self.assertEqual(search(db_path, "legacyonlymarker", top_k=10), [])
        self.assertEqual(search(db_path, "deletedonlymarker", top_k=10), [])

        new_results = search(db_path, "modernonlymarker", top_k=10)
        self.assertEqual(len(new_results), 1)
        self.assertEqual(new_results[0].path, "src/One.kt")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
