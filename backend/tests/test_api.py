from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = BACKEND_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

try:
    from fastapi.testclient import TestClient
    from reposage.api import create_app
except ImportError as exc:  # pragma: no cover - dependency availability check.
    TestClient = None
    create_app = None
    FASTAPI_IMPORT_ERROR = exc
else:
    FASTAPI_IMPORT_ERROR = None

from reposage.indexing import index_repository
from reposage.retrieval import search


@unittest.skipIf(TestClient is None, f"FastAPI test dependencies unavailable: {FASTAPI_IMPORT_ERROR}")
@unittest.skipIf(shutil.which("git") is None, "git is required for API tests")
class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        _git(self.repo, "init")
        self.db_path = self.root / "reposage.db"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_successful_retrieval_preserves_exact_citation_and_text(self) -> None:
        source = (
            "package sample\n"
            "\n"
            "class ErrorMapper {\n"
            "    fun mapHttpNotFound() = \"not found\"\n"
            "    fun mapRateLimited() = \"rate limited\"\n"
            "}\n"
        )
        _write(self.repo / "src/ErrorMapper.kt", source)
        _git(self.repo, "add", ".")
        index_repository(self.repo, self.db_path)

        with _client_for_db(self.db_path) as client:
            response = client.post(
                "/search",
                json={"query": "http not found rate limited", "top_k": 1},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["query"], "http not found rate limited")
        self.assertNotIn("repo_root", payload["index_metadata"])
        self.assertNotIn("db_path", payload["index_metadata"])
        self.assertIsInstance(payload["index_metadata"]["git_dirty"], bool)
        self.assertIsInstance(payload["index_metadata"]["files_indexed"], int)
        self.assertIsInstance(payload["index_metadata"]["chunks_indexed"], int)
        self.assertIsInstance(payload["index_metadata"]["git_head"], str)
        self.assertEqual(len(payload["results"]), 1)
        result = payload["results"][0]
        self.assertEqual(result["path"], "src/ErrorMapper.kt")
        self.assertEqual(result["citation"], "src/ErrorMapper.kt:L1-L6")
        self.assertEqual(result["text"], source)

    def test_empty_results_return_200(self) -> None:
        _write(self.repo / "src/CacheStore.kt", "package sample\n\nfun cacheOnly() = Unit\n")
        _git(self.repo, "add", ".")
        index_repository(self.repo, self.db_path)

        with _client_for_db(self.db_path) as client:
            response = client.post(
                "/search",
                json={"query": "unmatchedonlyterm", "top_k": 5},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])

    def test_invalid_input_returns_422(self) -> None:
        _write(self.repo / "src/CacheStore.kt", "package sample\n\nfun cacheOnly() = Unit\n")
        _git(self.repo, "add", ".")
        index_repository(self.repo, self.db_path)

        with _client_for_db(self.db_path) as client:
            blank = client.post("/search", json={"query": "   ", "top_k": 5})
            too_long = client.post("/search", json={"query": "x" * 2_001, "top_k": 5})
            too_large = client.post("/search", json={"query": "cache", "top_k": 21})
            too_small = client.post("/search", json={"query": "cache", "top_k": 0})

        self.assertEqual(blank.status_code, 422)
        self.assertEqual(too_long.status_code, 422)
        self.assertEqual(too_large.status_code, 422)
        self.assertEqual(too_small.status_code, 422)

    def test_unavailable_index_returns_safe_503_and_health_degraded(self) -> None:
        missing_path = self.root / "missing.db"

        with _client_for_db(missing_path) as client:
            search_response = client.post("/search", json={"query": "cache", "top_k": 5})
            health_response = client.get("/health")

        self.assertEqual(search_response.status_code, 503)
        self.assertNotIn(str(missing_path), search_response.text)
        self.assertIn("reposage index", search_response.text)
        self.assertEqual(health_response.status_code, 200)
        health_payload = health_response.json()
        self.assertFalse(health_payload["index_ready"])
        self.assertNotIn(str(missing_path), health_response.text)

    def test_api_and_cli_return_same_ordered_chunk_ids(self) -> None:
        _write(
            self.repo / "src/One.kt",
            "package sample\n\nfun cacheFreshnessChecker() = Unit\n",
        )
        _write(
            self.repo / "src/Two.kt",
            "package sample\n\nfun cacheFreshnessPolicy() = Unit\n",
        )
        _git(self.repo, "add", ".")
        index_repository(self.repo, self.db_path)

        query = "cache freshness"
        with _client_for_db(self.db_path) as client:
            api_response = client.post(
                "/search",
                json={"query": query, "top_k": 2},
            )

        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC_ROOT)
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "reposage.cli",
                "search",
                "--db",
                str(self.db_path),
                "--query",
                query,
                "--top-k",
                "2",
                "--json",
            ],
            check=True,
            text=True,
            capture_output=True,
            env=env,
        )
        cli_payload = json.loads(completed.stdout)
        direct_results = search(self.db_path, query, top_k=2)

        self.assertEqual(api_response.status_code, 200)
        api_chunk_ids = [result["chunk_id"] for result in api_response.json()["results"]]
        cli_chunk_ids = [result["chunk_id"] for result in cli_payload["results"]]
        direct_chunk_ids = [result.chunk_id for result in direct_results]
        self.assertEqual(api_chunk_ids, cli_chunk_ids)
        self.assertEqual(api_chunk_ids, direct_chunk_ids)


@contextmanager
def _client_for_db(db_path: Path):
    with patch.dict(os.environ, {"REPOSAGE_DB_PATH": str(db_path)}, clear=False):
        with TestClient(create_app()) as client:
            yield client


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
