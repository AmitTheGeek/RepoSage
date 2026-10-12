package com.reposage.app.data

import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SearchDtoParsingTest {
    @Test
    fun parsesActualApiResponseShapeWithTypedMetadata() {
        val response = Json {
            ignoreUnknownKeys = true
        }.decodeFromString<SearchResponseDto>(ACTUAL_API_RESPONSE)

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
