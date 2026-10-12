package com.reposage.app.ui

import androidx.lifecycle.SavedStateHandle
import com.reposage.app.data.IndexMetadata
import com.reposage.app.data.SearchError
import com.reposage.app.data.SearchPayload
import com.reposage.app.data.SearchRepository
import com.reposage.app.data.SearchRepositoryResult
import com.reposage.app.data.SearchResult
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.withContext
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TestWatcher
import org.junit.runner.Description

@OptIn(ExperimentalCoroutinesApi::class)
class SearchViewModelTest {
    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    @Test
    fun successfulSearchShowsResults() = runTest {
        val repository = FakeSearchRepository()
        val viewModel = SearchViewModel(repository, SavedStateHandle())
        collectState(viewModel)

        viewModel.onQuestionChanged("  How are errors mapped?  ")
        viewModel.onSearchClicked()
        advanceUntilIdle()

        repository.completeWith(
            payload = samplePayload(
                query = "How are errors mapped?",
                results = listOf(sampleResult()),
            ),
        )
        advanceUntilIdle()

        val content = viewModel.uiState.value.content
        assertTrue(content is SearchContentState.Results)
        content as SearchContentState.Results
        assertEquals("How are errors mapped?", content.payload.query)
        assertEquals("core/data/ErrorMapping.kt:L1-L42", content.payload.results.single().citation)
    }

    @Test
    fun emptySearchShowsExplicitEmptyState() = runTest {
        val repository = FakeSearchRepository()
        val viewModel = SearchViewModel(repository, SavedStateHandle())
        collectState(viewModel)

        viewModel.onQuestionChanged("no matches")
        viewModel.onSearchClicked()
        advanceUntilIdle()

        repository.completeWith(samplePayload(query = "no matches", results = emptyList()))
        advanceUntilIdle()

        val content = viewModel.uiState.value.content
        assertTrue(content is SearchContentState.Empty)
        content as SearchContentState.Empty
        assertEquals("no matches", content.submittedQuestion)
        assertEquals(107, content.metadata.filesIndexed)
    }

    @Test
    fun errorCanRetryFailedQuery() = runTest {
        val repository = FakeSearchRepository()
        val viewModel = SearchViewModel(repository, SavedStateHandle())
        collectState(viewModel)

        viewModel.onQuestionChanged("backend down")
        viewModel.onSearchClicked()
        advanceUntilIdle()
        repository.completeWith(SearchRepositoryResult.Failure(SearchError.ConnectionFailed))
        advanceUntilIdle()

        val error = viewModel.uiState.value.content
        assertTrue(error is SearchContentState.Error)
        error as SearchContentState.Error
        assertTrue(error.canRetry)

        viewModel.onRetry()
        advanceUntilIdle()
        repository.completeWith(
            payload = samplePayload(query = "backend down", results = listOf(sampleResult())),
            requestIndex = 1,
        )
        advanceUntilIdle()

        assertEquals(listOf("backend down", "backend down"), repository.requests.map { it.query })
        assertTrue(viewModel.uiState.value.content is SearchContentState.Results)
    }

    @Test
    fun olderSearchCannotOverwriteNewerResults() = runTest {
        val repository = FakeSearchRepository(ignoreCancellation = true)
        val viewModel = SearchViewModel(repository, SavedStateHandle())
        collectState(viewModel)

        viewModel.onQuestionChanged("first query")
        viewModel.onSearchClicked()
        advanceUntilIdle()
        viewModel.onQuestionChanged("second query")
        viewModel.onSearchClicked()
        advanceUntilIdle()

        repository.completeWith(
            payload = samplePayload(
                query = "second query",
                results = listOf(sampleResult(chunkId = "second")),
            ),
            requestIndex = 1,
        )
        advanceUntilIdle()
        repository.completeWith(
            payload = samplePayload(
                query = "first query",
                results = listOf(sampleResult(chunkId = "first")),
            ),
            requestIndex = 0,
        )
        advanceUntilIdle()

        val content = viewModel.uiState.value.content
        assertTrue(content is SearchContentState.Results)
        content as SearchContentState.Results
        assertEquals("second query", content.payload.query)
        assertEquals("second", content.payload.results.single().chunkId)
    }

    @Test
    fun savedDraftRestoresWithoutSubmittingSearch() = runTest {
        val repository = FakeSearchRepository()
        val savedStateHandle = SavedStateHandle(mapOf("draft_question" to "cached draft"))
        val viewModel = SearchViewModel(repository, savedStateHandle)
        collectState(viewModel)
        advanceUntilIdle()

        assertEquals("cached draft", viewModel.uiState.value.draftQuestion)
        assertTrue(viewModel.uiState.value.content is SearchContentState.Initial)
        assertTrue(repository.requests.isEmpty())
    }
}

private fun TestScope.collectState(viewModel: SearchViewModel) {
    backgroundScope.launch {
        viewModel.uiState.collect()
    }
}

private class FakeSearchRepository(
    private val ignoreCancellation: Boolean = false,
) : SearchRepository {
    val requests = mutableListOf<Request>()

    override suspend fun search(query: String, topK: Int): SearchRepositoryResult {
        val request = Request(
            query = query,
            topK = topK,
            result = CompletableDeferred(),
        )
        requests += request
        return if (ignoreCancellation) {
            withContext(NonCancellable) { request.result.await() }
        } else {
            request.result.await()
        }
    }

    fun completeWith(
        payload: SearchPayload,
        requestIndex: Int = 0,
    ) {
        completeWith(
            result = SearchRepositoryResult.Success(payload),
            requestIndex = requestIndex,
        )
    }

    fun completeWith(
        result: SearchRepositoryResult,
        requestIndex: Int = 0,
    ) {
        requests[requestIndex].result.complete(result)
    }

    data class Request(
        val query: String,
        val topK: Int,
        val result: CompletableDeferred<SearchRepositoryResult>,
    )
}

private fun samplePayload(
    query: String,
    results: List<SearchResult>,
): SearchPayload =
    SearchPayload(
        query = query,
        indexMetadata = IndexMetadata(
            gitDirty = false,
            filesIndexed = 107,
            chunksIndexed = 167,
            gitHead = "5d6f5ebc842f6cf4bd8d6f2b716e08043ac695f2",
        ),
        scoreDirection = "lower scores rank higher",
        results = results,
    )

private fun sampleResult(
    chunkId: String = "chunk-1",
): SearchResult =
    SearchResult(
        chunkId = chunkId,
        path = "core/data/ErrorMapping.kt",
        startLine = 1,
        endLine = 42,
        text = "fun mapError() = Unit\n",
        score = -38.37,
        citation = "core/data/ErrorMapping.kt:L1-L42",
    )

@OptIn(ExperimentalCoroutinesApi::class)
class MainDispatcherRule(
    private val testDispatcher: TestDispatcher = StandardTestDispatcher(),
) : TestWatcher() {
    override fun starting(description: Description) {
        Dispatchers.setMain(testDispatcher)
    }

    override fun finished(description: Description) {
        Dispatchers.resetMain()
    }
}
