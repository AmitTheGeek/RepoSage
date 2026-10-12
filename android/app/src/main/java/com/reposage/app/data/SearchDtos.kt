package com.reposage.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class SearchRequestDto(
    val query: String,
    @SerialName("top_k")
    val topK: Int,
)

@Serializable
data class SearchResponseDto(
    val query: String,
    @SerialName("index_metadata")
    val indexMetadata: IndexMetadataDto,
    @SerialName("score_direction")
    val scoreDirection: String,
    val results: List<SearchResultDto>,
)

@Serializable
data class IndexMetadataDto(
    @SerialName("git_dirty")
    val gitDirty: Boolean,
    @SerialName("files_indexed")
    val filesIndexed: Int,
    @SerialName("chunks_indexed")
    val chunksIndexed: Int,
    @SerialName("git_head")
    val gitHead: String,
)

@Serializable
data class SearchResultDto(
    @SerialName("chunk_id")
    val chunkId: String,
    val path: String,
    @SerialName("start_line")
    val startLine: Int,
    @SerialName("end_line")
    val endLine: Int,
    val text: String,
    val score: Double,
    val citation: String,
)

fun SearchResponseDto.toDomain(): SearchPayload =
    SearchPayload(
        query = query,
        indexMetadata = indexMetadata.toDomain(),
        scoreDirection = scoreDirection,
        results = results.map { it.toDomain() },
    )

private fun IndexMetadataDto.toDomain(): IndexMetadata =
    IndexMetadata(
        gitDirty = gitDirty,
        filesIndexed = filesIndexed,
        chunksIndexed = chunksIndexed,
        gitHead = gitHead,
    )

private fun SearchResultDto.toDomain(): SearchResult =
    SearchResult(
        chunkId = chunkId,
        path = path,
        startLine = startLine,
        endLine = endLine,
        text = text,
        score = score,
        citation = citation,
    )
