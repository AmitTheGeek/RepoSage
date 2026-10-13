package com.reposage.app.ui

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.createSavedStateHandle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.reposage.app.data.AnswerError
import com.reposage.app.data.AnswerPayload
import com.reposage.app.data.AnswerRepositoryResult
import com.reposage.app.data.AnswerStatus
import com.reposage.app.data.IndexMetadata
import com.reposage.app.data.SearchError
import com.reposage.app.data.SearchPayload
import com.reposage.app.data.SearchRepository
import com.reposage.app.data.SearchRepositoryResult
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class SearchViewModel(
    private val repository: SearchRepository,
    private val savedStateHandle: SavedStateHandle,
) : ViewModel() {
    private val draftQuestion = savedStateHandle.getStateFlow(DRAFT_QUESTION_KEY, "")
    private val searchState = MutableStateFlow<SearchContentState>(SearchContentState.Initial)
    private var searchJob: Job? = null
    private var activeRequestId = 0L
    private var lastSubmittedRequest: SubmittedRequest? = null

    val uiState: StateFlow<SearchUiState> =
        combine(draftQuestion, searchState) { draft, state ->
            SearchUiState(
                draftQuestion = draft,
                content = state,
            )
        }.stateIn(
            scope = viewModelScope,
            started = SharingStarted.Eagerly,
            initialValue = SearchUiState(),
        )

    fun onQuestionChanged(question: String) {
        savedStateHandle[DRAFT_QUESTION_KEY] = question
    }

    fun onSearchClicked() {
        submitCurrent(mode = RequestMode.SearchCode)
    }

    fun onAskClicked() {
        submitCurrent(mode = RequestMode.Ask)
    }

    private fun submitCurrent(mode: RequestMode) {
        val query = draftQuestion.value.trim()
        if (query.isBlank()) {
            searchState.value = SearchContentState.Error(
                submittedQuestion = "",
                mode = mode,
                message = "Enter a question to search the indexed repository.",
                canRetry = false,
            )
            return
        }
        submit(SubmittedRequest(query = query, mode = mode))
    }

    fun onRetry() {
        val request = lastSubmittedRequest ?: return
        submit(request)
    }

    private fun submit(request: SubmittedRequest) {
        lastSubmittedRequest = request
        val requestId = ++activeRequestId
        searchJob?.cancel()
        searchState.value = SearchContentState.Loading(
            submittedQuestion = request.query,
            mode = request.mode,
        )
        searchJob = viewModelScope.launch {
            val nextState = when (request.mode) {
                RequestMode.Ask -> answerStateFor(request)
                RequestMode.SearchCode -> searchStateFor(request)
            }
            if (requestId != activeRequestId) return@launch
            searchState.value = nextState
        }
    }

    private suspend fun searchStateFor(request: SubmittedRequest): SearchContentState =
        when (val result = repository.search(query = request.query, topK = DEFAULT_TOP_K)) {
            is SearchRepositoryResult.Success -> {
                if (result.payload.results.isEmpty()) {
                    SearchContentState.Empty(
                        submittedQuestion = result.payload.query,
                        metadata = result.payload.indexMetadata,
                    )
                } else {
                    SearchContentState.SearchResults(
                        payload = result.payload,
                    )
                }
            }
            is SearchRepositoryResult.Failure -> SearchContentState.Error(
                submittedQuestion = request.query,
                mode = request.mode,
                message = result.error.toMessage(),
                canRetry = true,
            )
        }

    private suspend fun answerStateFor(request: SubmittedRequest): SearchContentState =
        when (val result = repository.answer(query = request.query, topK = DEFAULT_TOP_K)) {
            is AnswerRepositoryResult.Success -> {
                when (result.payload.status) {
                    AnswerStatus.Answered -> SearchContentState.Answer(
                        payload = result.payload,
                    )
                    AnswerStatus.InsufficientEvidence -> SearchContentState.InsufficientEvidence(
                        payload = result.payload,
                    )
                    AnswerStatus.Unknown -> SearchContentState.Error(
                        submittedQuestion = request.query,
                        mode = request.mode,
                        message = "The backend returned an answer status this app does not understand.",
                        canRetry = true,
                    )
                }
            }
            is AnswerRepositoryResult.Failure -> SearchContentState.Error(
                submittedQuestion = request.query,
                mode = request.mode,
                message = result.error.toMessage(),
                canRetry = true,
            )
        }

    companion object {
        fun factory(repository: SearchRepository): ViewModelProvider.Factory =
            viewModelFactory {
                initializer {
                    SearchViewModel(
                        repository = repository,
                        savedStateHandle = createSavedStateHandle(),
                    )
                }
            }
    }
}

data class SearchUiState(
    val draftQuestion: String = "",
    val content: SearchContentState = SearchContentState.Initial,
)

sealed interface SearchContentState {
    data object Initial : SearchContentState
    data class Loading(
        val submittedQuestion: String,
        val mode: RequestMode,
    ) : SearchContentState
    data class SearchResults(val payload: SearchPayload) : SearchContentState
    data class Answer(val payload: AnswerPayload) : SearchContentState
    data class InsufficientEvidence(val payload: AnswerPayload) : SearchContentState
    data class Empty(
        val submittedQuestion: String,
        val metadata: IndexMetadata,
    ) : SearchContentState
    data class Error(
        val submittedQuestion: String,
        val mode: RequestMode,
        val message: String,
        val canRetry: Boolean,
    ) : SearchContentState
}

enum class RequestMode {
    Ask,
    SearchCode,
}

private data class SubmittedRequest(
    val query: String,
    val mode: RequestMode,
)

private fun SearchError.toMessage(): String =
    when (this) {
        SearchError.InvalidRequest -> "The backend rejected the question. Edit it and try again."
        SearchError.IndexUnavailable -> "The RepoSage index is unavailable. Start the backend with REPOSAGE_DB_PATH, then retry."
        SearchError.ConnectionFailed -> "Could not reach the RepoSage backend. Check the server connection and retry."
        SearchError.Timeout -> "The RepoSage backend timed out. Retry when it is responsive."
        SearchError.Unexpected -> "RepoSage search failed unexpectedly. Retry or check backend logs."
    }

private fun AnswerError.toMessage(): String =
    when (this) {
        AnswerError.InvalidRequest -> "The backend rejected the question. Edit it and try again."
        AnswerError.IndexUnavailable -> "The RepoSage index is unavailable. Start the backend with REPOSAGE_DB_PATH, then retry."
        AnswerError.GeminiNotConfigured -> "Answer generation is not configured on the backend. Set GEMINI_API_KEY in the backend process, then retry."
        AnswerError.QuotaOrRateLimited -> "Gemini quota or rate limit was reached. Retry later or check the backend key quota."
        AnswerError.GeminiTimeout -> "Gemini did not return before the backend timeout. Retry when the service is responsive."
        AnswerError.InvalidResponse -> "The backend could not validate the answer structure or source references. Retry or check backend logs."
        AnswerError.ProviderFailure -> "Gemini answer generation failed on the backend. Check the model/key configuration and backend logs."
        AnswerError.ConnectionFailed -> "Could not reach the RepoSage backend. Check the server connection and retry."
        AnswerError.Timeout -> "The RepoSage backend timed out. Retry when it is responsive."
        AnswerError.Unexpected -> "RepoSage answer generation failed unexpectedly. Retry or check backend logs."
    }

private const val DRAFT_QUESTION_KEY = "draft_question"
private const val DEFAULT_TOP_K = 5
