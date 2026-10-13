package com.reposage.app.data

import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SearchDtoParsingTest {
    @Test
    fun parsesActualApiResponseShapeWithTypedMetadata() {
        val response = TEST_JSON.decodeFromString<SearchResponseDto>(ACTUAL_API_RESPONSE)

        assertEquals(
            "How are GitHub HTTP errors mapped to DevPulse errors like rate limited, not found, and server error?",
            response.query,
        )
        assertFalse(response.indexMetadata.gitDirty)
        assertEquals(107, response.indexMetadata.filesIndexed)
        assertEquals(167, response.indexMetadata.chunksIndexed)
        assertEquals(
            "5d6f5ebc842f6cf4bd8d6f2b716e08043ac695f2",
            response.indexMetadata.gitHead,
        )
        assertEquals("c554bbc23b3a13a918e17a14", response.results.single().chunkId)
        assertTrue(response.results.single().text.contains("toDevPulseError"))

        val domain = response.toDomain()
        assertEquals("core/data/src/main/java/com/devpulse/core/data/error/ErrorMapping.kt", domain.results.single().path)
        assertEquals("core/data/src/main/java/com/devpulse/core/data/error/ErrorMapping.kt:L1-L42", domain.results.single().citation)
    }

    @Test
    fun parsesAnswerApiResponseShapeAndMapsClaimSources() {
        val response = TEST_JSON.decodeFromString<AnswerResponseDto>(ANSWER_API_RESPONSE)

        assertEquals("answered", response.status)
        assertEquals("gemini-test", response.modelId)
        assertEquals("S1", response.claims.single().sourceIds.single())
        assertEquals("core/data/ErrorMapping.kt:L1-L42", response.sources.single().citation)

        val domain = response.toDomain()
        assertEquals(AnswerStatus.Answered, domain.status)
        assertEquals("HTTP errors are mapped to DevPulse errors in ErrorMapping.", domain.claims.single().text)
        assertEquals("fun mapError() = Unit\n", domain.sourceFor("S1")?.text)
    }

    @Test
    fun parsesInsufficientEvidenceAnswerResponseShape() {
        val response = TEST_JSON.decodeFromString<AnswerResponseDto>(INSUFFICIENT_EVIDENCE_RESPONSE)

        val domain = response.toDomain()
        assertEquals(AnswerStatus.InsufficientEvidence, domain.status)
        assertTrue(domain.claims.isEmpty())
        assertTrue(domain.sources.isEmpty())
        assertEquals("gemini-test", domain.modelId)
    }

    @Test
    fun parsesAnswerErrorContractCode() {
        val error = TEST_JSON.decodeFromString<ErrorResponseDto>(ANSWER_ERROR_RESPONSE)

        assertEquals("gemini_invalid_response", error.detail?.code)
        assertEquals("Gemini returned an answer whose structure or source references could not be validated.", error.detail?.message)
    }
}

private val TEST_JSON = Json {
    ignoreUnknownKeys = true
}

private const val ACTUAL_API_RESPONSE = """
{
  "query": "How are GitHub HTTP errors mapped to DevPulse errors like rate limited, not found, and server error?",
  "index_metadata": {
    "chunk_lines": 80,
    "chunks_indexed": 167,
    "files_indexed": 107,
    "git_dirty": false,
    "git_head": "5d6f5ebc842f6cf4bd8d6f2b716e08043ac695f2",
    "indexed_at_utc": "2026-10-10T11:40:56+00:00",
    "overlap_lines": 15,
    "schema_version": "1"
  },
  "score_direction": "lower scores rank higher; scores are adjusted SQLite FTS5 BM25 ranking values, not confidence",
  "results": [
    {
      "chunk_id": "c554bbc23b3a13a918e17a14",
      "path": "core/data/src/main/java/com/devpulse/core/data/error/ErrorMapping.kt",
      "start_line": 1,
      "end_line": 42,
      "text": "package com.devpulse.core.data.error\n\ninternal fun Throwable.toDevPulseError(): DevPulseError =\n    when (this) {\n        is IOException -> DevPulseError.NetworkUnavailable\n        is HttpException -> toHttpError()\n        is SQLException -> DevPulseError.LocalStorageError(this)\n        else -> DevPulseError.Unknown(this)\n    }\n",
      "score": -38.37066020036226,
      "citation": "core/data/src/main/java/com/devpulse/core/data/error/ErrorMapping.kt:L1-L42"
    }
  ]
}
"""

private const val ANSWER_API_RESPONSE = """
{
  "query": "How are errors mapped?",
  "status": "answered",
  "model_id": "gemini-test",
  "index_metadata": {
    "chunk_lines": 80,
    "chunks_indexed": 167,
    "files_indexed": 107,
    "git_dirty": false,
    "git_head": "5d6f5ebc842f6cf4bd8d6f2b716e08043ac695f2",
    "indexed_at_utc": "2026-10-10T11:40:56+00:00",
    "overlap_lines": 15,
    "schema_version": "1"
  },
  "score_direction": "lower scores rank higher; scores are adjusted SQLite FTS5 BM25 ranking values, not confidence",
  "claims": [
    {
      "text": "HTTP errors are mapped to DevPulse errors in ErrorMapping.",
      "source_ids": ["S1"],
      "citations": ["core/data/ErrorMapping.kt:L1-L42"]
    }
  ],
  "sources": [
    {
      "source_id": "S1",
      "chunk_id": "chunk-1",
      "path": "core/data/ErrorMapping.kt",
      "start_line": 1,
      "end_line": 42,
      "text": "fun mapError() = Unit\n",
      "score": -38.37,
      "citation": "core/data/ErrorMapping.kt:L1-L42"
    }
  ],
  "usage": {
    "total_token_count": 42
  },
  "latency_ms": 123
}
"""

private const val INSUFFICIENT_EVIDENCE_RESPONSE = """
{
  "query": "Does OAuth exist?",
  "status": "insufficient_evidence",
  "model_id": "gemini-test",
  "index_metadata": {
    "chunks_indexed": 167,
    "files_indexed": 107,
    "git_dirty": false,
    "git_head": "5d6f5ebc842f6cf4bd8d6f2b716e08043ac695f2"
  },
  "score_direction": "lower scores rank higher",
  "claims": [],
  "sources": [],
  "usage": null,
  "latency_ms": 99
}
"""

private const val ANSWER_ERROR_RESPONSE = """
{
  "detail": {
    "code": "gemini_invalid_response",
    "message": "Gemini returned an answer whose structure or source references could not be validated."
  }
}
"""
