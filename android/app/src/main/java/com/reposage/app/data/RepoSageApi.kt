package com.reposage.app.data

import retrofit2.http.Body
import retrofit2.http.POST

interface RepoSageApi {
    @POST("search")
    suspend fun search(@Body request: SearchRequestDto): SearchResponseDto
}
