package com.reposage.app.data

import java.io.IOException
import java.net.SocketTimeoutException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import retrofit2.HttpException

class NetworkSearchRepository(
    private val api: RepoSageApi,
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO,
) : SearchRepository {
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
}

private fun HttpException.toSearchError(): SearchError =
    when (code()) {
        HTTP_UNPROCESSABLE_ENTITY -> SearchError.InvalidRequest
        HTTP_SERVICE_UNAVAILABLE -> SearchError.IndexUnavailable
        else -> SearchError.Unexpected
    }

private const val HTTP_UNPROCESSABLE_ENTITY = 422
private const val HTTP_SERVICE_UNAVAILABLE = 503
