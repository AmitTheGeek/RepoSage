package com.reposage.app.data

data class SearchPayload(
    val query: String,
    val indexMetadata: IndexMetadata,
    val scoreDirection: String,
    val results: List<SearchResult>,
)

data class IndexMetadata(
    val gitDirty: Boolean,
    val filesIndexed: Int,
    val chunksIndexed: Int,
    val gitHead: String,
)

data class SearchResult(
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

sealed interface SearchError {
    data object InvalidRequest : SearchError
    data object IndexUnavailable : SearchError
    data object ConnectionFailed : SearchError
    data object Timeout : SearchError
    data object Unexpected : SearchError
}

interface SearchRepository {
    suspend fun search(query: String, topK: Int): SearchRepositoryResult
}
