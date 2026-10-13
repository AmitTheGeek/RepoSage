from __future__ import annotations

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

from reposage.answering import (
    AnswerProviderNotConfigured,
    AnswerProviderQuotaError,
    AnswerProviderTimeout,
    InvalidAnswerResponse,
    ProviderAnswer,
    ProviderClaim,
    build_evidence_sources,
    provider_answer_from_payload,
)
from reposage.indexing import index_repository
from reposage.models import SearchResult


@unittest.skipIf(TestClient is None, f"FastAPI test dependencies unavailable: {FASTAPI_IMPORT_ERROR}")
@unittest.skipIf(shutil.which("git") is None, "git is required for answer API tests")
class AnswerApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        _git(self.repo, "init")
        self.db_path = self.root / "reposage.db"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_supported_claims_resolve_citations_from_supplied_sources(self) -> None:
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
        provider = RecordingProvider(
            ProviderAnswer(
                status="answered",
                claims=(
                    ProviderClaim(
                        text="HTTP not-found and rate-limit handling is implemented in ErrorMapper.",
                        source_ids=("S1",),
                    ),
                ),
                usage={"total_token_count": 42},
                latency_ms=123,
            ),
        )

        with _client_for_db(self.db_path, provider) as client:
            response = client.post(
                "/answer",
                json={"query": "http not found rate limited", "top_k": 1},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "answered")
        self.assertEqual(payload["model_id"], "fake-answer-model")
        self.assertEqual(payload["usage"], {"total_token_count": 42})
        self.assertEqual(payload["latency_ms"], 123)
        self.assertEqual(payload["claims"][0]["source_ids"], ["S1"])
        self.assertEqual(payload["claims"][0]["citations"], ["src/ErrorMapper.kt:L1-L6"])
        self.assertEqual(payload["sources"][0]["source_id"], "S1")
        self.assertEqual(payload["sources"][0]["text"], source)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(provider.last_sources[0].citation, "src/ErrorMapper.kt:L1-L6")

    def test_provider_can_abstain_even_with_retrieved_evidence(self) -> None:
        _write(self.repo / "src/CacheStore.kt", "package sample\n\nfun cacheOnly() = Unit\n")
        _git(self.repo, "add", ".")
        index_repository(self.repo, self.db_path)
        provider = RecordingProvider(
            ProviderAnswer(status="insufficient_evidence", claims=()),
        )

        with _client_for_db(self.db_path, provider) as client:
            response = client.post("/answer", json={"query": "cache", "top_k": 1})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "insufficient_evidence")
        self.assertEqual(payload["claims"], [])
        self.assertEqual(len(payload["sources"]), 1)
        self.assertEqual(provider.calls, 1)

    def test_no_matches_return_insufficient_evidence_without_provider_call(self) -> None:
        _write(self.repo / "src/CacheStore.kt", "package sample\n\nfun cacheOnly() = Unit\n")
        _git(self.repo, "add", ".")
        index_repository(self.repo, self.db_path)
        factory = ProviderFactory(RecordingProvider(ProviderAnswer(status="answered", claims=())))

        with _client_for_db(self.db_path, factory=factory) as client:
            response = client.post(
                "/answer",
                json={"query": "unmatchedonlyterm", "top_k": 5},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "insufficient_evidence")
        self.assertEqual(payload["claims"], [])
        self.assertEqual(payload["sources"], [])
        self.assertEqual(factory.calls, 0)

    def test_unknown_source_reference_returns_safe_error(self) -> None:
        _write(self.repo / "src/CacheStore.kt", "package sample\n\nfun cacheOnly() = Unit\n")
        _git(self.repo, "add", ".")
        index_repository(self.repo, self.db_path)
        provider = RecordingProvider(
            ProviderAnswer(
                status="answered",
                claims=(ProviderClaim(text="Cache exists.", source_ids=("S404",)),),
            ),
        )

        with _client_for_db(self.db_path, provider) as client:
            response = client.post("/answer", json={"query": "cache", "top_k": 1})

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"]["code"], "gemini_invalid_response")
        self.assertNotIn("src/CacheStore.kt", response.text)

    def test_malformed_provider_output_returns_safe_error(self) -> None:
        _write(self.repo / "src/CacheStore.kt", "package sample\n\nfun cacheOnly() = Unit\n")
        _git(self.repo, "add", ".")
        index_repository(self.repo, self.db_path)
        provider = RaisingProvider(InvalidAnswerResponse("bad shape"))

        with _client_for_db(self.db_path, provider) as client:
            response = client.post("/answer", json={"query": "cache", "top_k": 1})

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"]["code"], "gemini_invalid_response")
        self.assertNotIn("bad shape", response.text)

    def test_timeout_and_quota_failures_return_documented_error_codes(self) -> None:
        _write(self.repo / "src/CacheStore.kt", "package sample\n\nfun cacheOnly() = Unit\n")
        _git(self.repo, "add", ".")
        index_repository(self.repo, self.db_path)

        with _client_for_db(self.db_path, RaisingProvider(AnswerProviderTimeout("slow"))) as client:
            timeout_response = client.post("/answer", json={"query": "cache", "top_k": 1})
        with _client_for_db(self.db_path, RaisingProvider(AnswerProviderQuotaError("quota"))) as client:
            quota_response = client.post("/answer", json={"query": "cache", "top_k": 1})

        self.assertEqual(timeout_response.status_code, 504)
        self.assertEqual(timeout_response.json()["detail"]["code"], "gemini_timeout")
        self.assertEqual(quota_response.status_code, 429)
        self.assertEqual(quota_response.json()["detail"]["code"], "gemini_quota_or_rate_limited")

    def test_missing_gemini_configuration_returns_safe_503(self) -> None:
        _write(self.repo / "src/CacheStore.kt", "package sample\n\nfun cacheOnly() = Unit\n")
        _git(self.repo, "add", ".")
        index_repository(self.repo, self.db_path)
        provider = RaisingProvider(AnswerProviderNotConfigured("missing key"))

        with _client_for_db(self.db_path, provider) as client:
            response = client.post("/answer", json={"query": "cache", "top_k": 1})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "gemini_not_configured")
        self.assertNotIn("missing key", response.text)


class AnsweringUnitTests(unittest.TestCase):
    def test_context_budget_deduplicates_and_omits_whole_chunks(self) -> None:
        first = SearchResult(
            chunk_id="a",
            path="src/One.kt",
            start_line=1,
            end_line=2,
            text="fun cacheOnly() = Unit\n",
            score=-1.0,
            citation="src/One.kt:L1-L2",
        )
        duplicate = SearchResult(
            chunk_id="a",
            path="src/One.kt",
            start_line=1,
            end_line=2,
            text="fun cacheOnly() = Unit\n",
            score=-1.0,
            citation="src/One.kt:L1-L2",
        )
        oversized = SearchResult(
            chunk_id="b",
            path="src/Two.kt",
            start_line=1,
            end_line=500,
            text="x" * 1_000,
            score=-0.5,
            citation="src/Two.kt:L1-L500",
        )

        sources = build_evidence_sources(
            [first, duplicate, oversized],
            context_char_budget=200,
        )

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].source_id, "S1")
        self.assertEqual(sources[0].chunk_id, "a")
        self.assertEqual(sources[0].text, "fun cacheOnly() = Unit\n")

    def test_malformed_payload_is_rejected_before_validation(self) -> None:
        with self.assertRaises(InvalidAnswerResponse):
            provider_answer_from_payload({"status": "answered", "claims": [{"text": "x"}]})


class RecordingProvider:
    def __init__(self, answer: ProviderAnswer) -> None:
        self._answer = answer
        self.calls = 0
        self.last_query: str | None = None
        self.last_sources = ()

    @property
    def model_id(self) -> str:
        return "fake-answer-model"

    def generate_answer(self, *, query: str, sources):
        self.calls += 1
        self.last_query = query
        self.last_sources = sources
        return self._answer


class RaisingProvider:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    @property
    def model_id(self) -> str:
        return "fake-answer-model"

    def generate_answer(self, *, query: str, sources):
        raise self._exc


class ProviderFactory:
    def __init__(self, provider) -> None:
        self._provider = provider
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self._provider


@contextmanager
def _client_for_db(db_path: Path, provider=None, *, factory=None):
    provider_factory = factory if factory is not None else lambda: provider
    with patch.dict(os.environ, {"REPOSAGE_DB_PATH": str(db_path)}, clear=False):
        with TestClient(create_app(answer_provider_factory=provider_factory)) as client:
            yield client


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
