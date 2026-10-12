package com.reposage.app.ui

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.createSavedStateHandle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.reposage.app.data.IndexMetadata
import com.reposage.app.data.SearchError
import com.reposage.app.data.SearchPayload
import com.reposage.app.data.SearchRepository
import com.reposage.app.data.SearchRepositoryResult
import com.reposage.app.data.SearchResult
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class SearchViewModel(
    private val repository: SearchRepository,
    private val savedStateHandle: SavedStateHandle,
) : ViewModel() {
    private val draftQuestion = savedStateHandle.getStateFlow(DRAFT_QUESTION_KEY, "")
    private val searchState = MutableStateFlow<SearchContentState>(SearchContentState.Initial)
    private var searchJob: Job? = null
    private var activeRequestId = 0L
    private var lastSubmittedQuestion: String? = null

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
        val query = draftQuestion.value.trim()
        if (query.isBlank()) {
            searchState.value = SearchContentState.Error(
                submittedQuestion = "",
                message = "Enter a question to search the indexed repository.",
                canRetry = false,
            )
            return
        }
        submit(query)
    }

    fun onRetry() {
        val query = lastSubmittedQuestion ?: return
        submit(query)
    }

    private fun submit(query: String) {
        lastSubmittedQuestion = query
        val requestId = ++activeRequestId
        searchJob?.cancel()
        searchState.value = SearchContentState.Loading(query)
        searchJob = viewModelScope.launch {
            val result = repository.search(query = query, topK = DEFAULT_TOP_K)
            if (requestId != activeRequestId) return@launch

            searchState.update {
                when (result) {
                    is SearchRepositoryResult.Success -> {
                        if (result.payload.results.isEmpty()) {
                            SearchContentState.Empty(
                                submittedQuestion = result.payload.query,
                                metadata = result.payload.indexMetadata,
                            )
                        } else {
                            SearchContentState.Results(
                                payload = result.payload,
                            )
                        }
                    }
                    is SearchRepositoryResult.Failure -> SearchContentState.Error(
                        submittedQuestion = query,
                        message = result.error.toMessage(),
                        canRetry = true,
                    )
                }
            }
        }
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
    data class Loading(val submittedQuestion: String) : SearchContentState
    data class Results(val payload: SearchPayload) : SearchContentState
    data class Empty(
        val submittedQuestion: String,
        val metadata: IndexMetadata,
    ) : SearchContentState
    data class Error(
        val submittedQuestion: String,
        val message: String,
        val canRetry: Boolean,
    ) : SearchContentState
}

private fun SearchError.toMessage(): String =
    when (this) {
        SearchError.InvalidRequest -> "The backend rejected the question. Edit it and try again."
        SearchError.IndexUnavailable -> "The RepoSage index is unavailable. Start the backend with REPOSAGE_DB_PATH, then retry."
        SearchError.ConnectionFailed -> "Could not reach the RepoSage backend. Check the server connection and retry."
        SearchError.Timeout -> "The RepoSage backend timed out. Retry when it is responsive."
        SearchError.Unexpected -> "RepoSage search failed unexpectedly. Retry or check backend logs."
    }

private const val DRAFT_QUESTION_KEY = "draft_question"
private const val DEFAULT_TOP_K = 5
