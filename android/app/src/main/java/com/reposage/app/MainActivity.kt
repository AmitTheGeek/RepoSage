package com.reposage.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.remember
import androidx.lifecycle.viewmodel.compose.viewModel
import com.reposage.app.data.SearchRepositoryFactory
import com.reposage.app.ui.SearchScreen
import com.reposage.app.ui.SearchViewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface {
                    val repository = remember {
                        SearchRepositoryFactory.create(BuildConfig.BACKEND_BASE_URL)
                    }
                    val viewModel: SearchViewModel = viewModel(
                        factory = SearchViewModel.factory(repository),
                    )
                    SearchScreen(viewModel = viewModel)
                }
            }
        }
    }
}
