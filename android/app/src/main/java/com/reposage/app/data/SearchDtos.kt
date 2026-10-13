package com.reposage.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

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
data class AnswerResponseDto(
    val query: String,
    val status: String,
    @SerialName("model_id")
    val modelId: String,
    @SerialName("index_metadata")
    val indexMetadata: IndexMetadataDto,
    @SerialName("score_direction")
    val scoreDirection: String,
    val claims: List<AnswerClaimDto>,
    val sources: List<AnswerSourceDto>,
    val usage: JsonObject? = null,
    @SerialName("latency_ms")
    val latencyMs: Int? = null,
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

@Serializable
data class AnswerClaimDto(
    val text: String,
    @SerialName("source_ids")
    val sourceIds: List<String>,
    val citations: List<String>,
)

@Serializable
data class AnswerSourceDto(
    @SerialName("source_id")
    val sourceId: String,
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

@Serializable
data class ErrorResponseDto(
    val detail: ErrorDetailDto? = null,
)

@Serializable
data class ErrorDetailDto(
    val code: String? = null,
    val message: String? = null,
)

fun SearchResponseDto.toDomain(): SearchPayload =
    SearchPayload(
        query = query,
        indexMetadata = indexMetadata.toDomain(),
        scoreDirection = scoreDirection,
        results = results.map { it.toDomain() },
    )

fun AnswerResponseDto.toDomain(): AnswerPayload =
    AnswerPayload(
        query = query,
        status = status.toAnswerStatus(),
        modelId = modelId,
        indexMetadata = indexMetadata.toDomain(),
        scoreDirection = scoreDirection,
        claims = claims.map { it.toDomain() },
        sources = sources.map { it.toDomain() },
        latencyMs = latencyMs,
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

private fun AnswerClaimDto.toDomain(): AnswerClaim =
    AnswerClaim(
        text = text,
        sourceIds = sourceIds,
        citations = citations,
    )

private fun AnswerSourceDto.toDomain(): AnswerSource =
    AnswerSource(
        sourceId = sourceId,
        chunkId = chunkId,
        path = path,
        startLine = startLine,
        endLine = endLine,
        text = text,
        score = score,
        citation = citation,
    )

private fun String.toAnswerStatus(): AnswerStatus =
    when (this) {
        "answered" -> AnswerStatus.Answered
        "insufficient_evidence" -> AnswerStatus.InsufficientEvidence
        else -> AnswerStatus.Unknown
    }
