package com.reposage.app.data

data class SearchPayload(
    val query: String,
    val indexMetadata: IndexMetadata,
    val scoreDirection: String,
    val results: List<SearchResult>,
)

data class AnswerPayload(
    val query: String,
    val status: AnswerStatus,
    val modelId: String,
    val indexMetadata: IndexMetadata,
    val scoreDirection: String,
    val claims: List<AnswerClaim>,
    val sources: List<AnswerSource>,
    val latencyMs: Int?,
) {
    fun sourceFor(sourceId: String): AnswerSource? =
        sources.firstOrNull { it.sourceId == sourceId }
}

data class IndexMetadata(
    val gitDirty: Boolean,
    val filesIndexed: Int,
    val chunksIndexed: Int,
    val gitHead: String,
)

enum class AnswerStatus {
    Answered,
    InsufficientEvidence,
    Unknown,
}

data class SearchResult(
    val chunkId: String,
    val path: String,
    val startLine: Int,
    val endLine: Int,
    val text: String,
    val score: Double,
    val citation: String,
)

data class AnswerClaim(
    val text: String,
    val sourceIds: List<String>,
    val citations: List<String>,
)

data class AnswerSource(
    val sourceId: String,
    val chunkId: String,
    val path: String,
    val startLine: Int,
    val endLine: Int,
    val text: String,
    val score: Double,
    val citation: String,
)

sealed interface SearchRepositoryResult {
    data class Success(val payload: SearchPayload) : SearchRepositoryResult
    data class Failure(val error: SearchError) : SearchRepositoryResult
}

sealed interface AnswerRepositoryResult {
    data class Success(val payload: AnswerPayload) : AnswerRepositoryResult
    data class Failure(val error: AnswerError) : AnswerRepositoryResult
}

sealed interface SearchError {
    data object InvalidRequest : SearchError
    data object IndexUnavailable : SearchError
    data object ConnectionFailed : SearchError
    data object Timeout : SearchError
    data object Unexpected : SearchError
}

sealed interface AnswerError {
    data object InvalidRequest : AnswerError
    data object IndexUnavailable : AnswerError
    data object GeminiNotConfigured : AnswerError
    data object QuotaOrRateLimited : AnswerError
    data object GeminiTimeout : AnswerError
    data object InvalidResponse : AnswerError
    data object ProviderFailure : AnswerError
    data object ConnectionFailed : AnswerError
    data object Timeout : AnswerError
    data object Unexpected : AnswerError
}

interface SearchRepository {
    suspend fun search(query: String, topK: Int): SearchRepositoryResult
    suspend fun answer(query: String, topK: Int): AnswerRepositoryResult
}
