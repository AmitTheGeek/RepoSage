package com.reposage.app.data

import java.io.IOException
import java.net.SocketTimeoutException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.Json
import retrofit2.HttpException

class NetworkSearchRepository(
    private val api: RepoSageApi,
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO,
) : SearchRepository {
    private val errorJson = Json {
        ignoreUnknownKeys = true
    }

    override suspend fun search(query: String, topK: Int): SearchRepositoryResult =
        withContext(ioDispatcher) {
            try {
                SearchRepositoryResult.Success(
                    api.search(SearchRequestDto(query = query, topK = topK)).toDomain(),
                )
            } catch (exception: HttpException) {
                SearchRepositoryResult.Failure(exception.toSearchError())
            } catch (exception: SocketTimeoutException) {
                SearchRepositoryResult.Failure(SearchError.Timeout)
            } catch (exception: IOException) {
                SearchRepositoryResult.Failure(SearchError.ConnectionFailed)
            } catch (exception: CancellationException) {
                throw exception
            } catch (exception: Exception) {
                SearchRepositoryResult.Failure(SearchError.Unexpected)
            }
        }

    override suspend fun answer(query: String, topK: Int): AnswerRepositoryResult =
        withContext(ioDispatcher) {
            try {
                AnswerRepositoryResult.Success(
                    api.answer(SearchRequestDto(query = query, topK = topK)).toDomain(),
                )
            } catch (exception: HttpException) {
                AnswerRepositoryResult.Failure(exception.toAnswerError(errorJson))
            } catch (exception: SocketTimeoutException) {
                AnswerRepositoryResult.Failure(AnswerError.Timeout)
            } catch (exception: IOException) {
                AnswerRepositoryResult.Failure(AnswerError.ConnectionFailed)
            } catch (exception: CancellationException) {
                throw exception
            } catch (exception: SerializationException) {
                AnswerRepositoryResult.Failure(AnswerError.InvalidResponse)
            } catch (exception: Exception) {
                AnswerRepositoryResult.Failure(AnswerError.Unexpected)
            }
        }
}

private fun HttpException.toSearchError(): SearchError =
    when (code()) {
        HTTP_UNPROCESSABLE_ENTITY -> SearchError.InvalidRequest
        HTTP_SERVICE_UNAVAILABLE -> SearchError.IndexUnavailable
        else -> SearchError.Unexpected
    }

private fun HttpException.toAnswerError(json: Json): AnswerError {
    val detailCode = errorDetailCode(json)
    return when (code()) {
        HTTP_UNPROCESSABLE_ENTITY -> AnswerError.InvalidRequest
        HTTP_TOO_MANY_REQUESTS -> AnswerError.QuotaOrRateLimited
        HTTP_GATEWAY_TIMEOUT -> AnswerError.GeminiTimeout
        HTTP_SERVICE_UNAVAILABLE -> {
            if (detailCode == ERROR_GEMINI_NOT_CONFIGURED) {
                AnswerError.GeminiNotConfigured
            } else {
                AnswerError.IndexUnavailable
            }
        }
        HTTP_BAD_GATEWAY -> {
            when (detailCode) {
                ERROR_GEMINI_INVALID_RESPONSE -> AnswerError.InvalidResponse
                ERROR_GEMINI_PROVIDER_FAILURE -> AnswerError.ProviderFailure
                else -> AnswerError.Unexpected
            }
        }
        else -> AnswerError.Unexpected
    }
}

private fun HttpException.errorDetailCode(json: Json): String? {
    val body = response()?.errorBody()?.string() ?: return null
    return try {
        json.decodeFromString<ErrorResponseDto>(body).detail?.code
    } catch (exception: SerializationException) {
        null
    } catch (exception: IllegalArgumentException) {
        null
    }
}

private const val HTTP_BAD_GATEWAY = 502
private const val HTTP_UNPROCESSABLE_ENTITY = 422
private const val HTTP_TOO_MANY_REQUESTS = 429
private const val HTTP_SERVICE_UNAVAILABLE = 503
private const val HTTP_GATEWAY_TIMEOUT = 504

private const val ERROR_GEMINI_INVALID_RESPONSE = "gemini_invalid_response"
private const val ERROR_GEMINI_NOT_CONFIGURED = "gemini_not_configured"
private const val ERROR_GEMINI_PROVIDER_FAILURE = "gemini_provider_failure"
