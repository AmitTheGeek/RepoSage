package com.reposage.app.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.ComposeTestRule
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import androidx.lifecycle.SavedStateHandle
import com.reposage.app.data.SearchRepositoryFactory
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Rule
import org.junit.Test

class SearchScreenMockServerTest {
    @get:Rule
    val composeRule = createComposeRule()

    private val server = MockWebServer()

    @After
    fun tearDown() {
        server.shutdown()
    }

    @Test
    fun answerCitationOpensMatchingSourceCode() {
        server.enqueue(jsonResponse(ANSWER_RESPONSE))
        setContent()

        composeRule.onNodeWithTag("question-input").performTextInput("How are errors mapped?")
        composeRule.onNodeWithText("Ask").performClick()

        composeRule.waitForText("HTTP errors are mapped to DevPulse errors in ErrorMapping.")
        composeRule.onNodeWithText("S1").performClick()

        composeRule.onNodeWithTag("answer-source-detail").assertIsDisplayed()
        composeRule.onNodeWithText("core/data/ErrorMapping.kt:L1-L42").assertIsDisplayed()
        composeRule.onNodeWithText("fun mapError() = Unit").assertIsDisplayed()
    }

    @Test
    fun insufficientEvidenceAnswerShowsAbstentionState() {
        server.enqueue(jsonResponse(INSUFFICIENT_RESPONSE))
        setContent()

        composeRule.onNodeWithTag("question-input").performTextInput("Does OAuth exist?")
        composeRule.onNodeWithText("Ask").performClick()

        composeRule.waitForText("Insufficient evidence in the retrieved source chunks to answer this question.")
        composeRule.onNodeWithText("This is an abstention from the supplied evidence, not proof that the feature is absent.").assertIsDisplayed()
        composeRule.onNodeWithText("Model gemini-test").assertIsDisplayed()
    }

    @Test
    fun searchCodeStillShowsRetrievedSourceResults() {
        server.enqueue(jsonResponse(SEARCH_RESPONSE))
        setContent()

        composeRule.onNodeWithTag("question-input").performTextInput("How are errors mapped?")
        composeRule.onNodeWithText("Search code").performClick()

        composeRule.waitForText("core/data/ErrorMapping.kt:L1-L42")
        composeRule.onNodeWithText("Expand code").performClick()
        composeRule.onNodeWithText("fun mapError() = Unit").assertIsDisplayed()
    }

    private fun setContent() {
        val repository = SearchRepositoryFactory.create(server.url("/").toString())
        val viewModel = SearchViewModel(repository, SavedStateHandle())
        composeRule.setContent {
            MaterialTheme {
                Surface {
                    SearchScreen(viewModel = viewModel)
                }
            }
        }
    }

    private fun jsonResponse(body: String): MockResponse =
        MockResponse()
            .setResponseCode(200)
            .setHeader("Content-Type", "application/json")
            .setBody(body)
}

private fun ComposeTestRule.waitForText(text: String) {
    waitUntil(timeoutMillis = 5_000) {
        onAllNodesWithText(text).fetchSemanticsNodes().isNotEmpty()
    }
}

private const val ANSWER_RESPONSE = """
{
  "query": "How are errors mapped?",
  "status": "answered",
  "model_id": "gemini-test",
  "index_metadata": {
    "chunks_indexed": 167,
    "files_indexed": 107,
    "git_dirty": false,
    "git_head": "5d6f5ebc842f6cf4bd8d6f2b716e08043ac695f2"
  },
  "score_direction": "lower scores rank higher",
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
      "text": "fun mapError() = Unit",
      "score": -38.37,
      "citation": "core/data/ErrorMapping.kt:L1-L42"
    }
  ],
  "usage": null,
  "latency_ms": 123
}
"""

private const val INSUFFICIENT_RESPONSE = """
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

private const val SEARCH_RESPONSE = """
{
  "query": "How are errors mapped?",
  "index_metadata": {
    "chunks_indexed": 167,
    "files_indexed": 107,
    "git_dirty": false,
    "git_head": "5d6f5ebc842f6cf4bd8d6f2b716e08043ac695f2"
  },
  "score_direction": "lower scores rank higher",
  "results": [
    {
      "chunk_id": "chunk-1",
      "path": "core/data/ErrorMapping.kt",
      "start_line": 1,
      "end_line": 42,
      "text": "fun mapError() = Unit",
      "score": -38.37,
      "citation": "core/data/ErrorMapping.kt:L1-L42"
    }
  ]
}
"""
