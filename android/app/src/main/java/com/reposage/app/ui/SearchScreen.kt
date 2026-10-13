package com.reposage.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.reposage.app.data.AnswerPayload
import com.reposage.app.data.AnswerSource
import com.reposage.app.data.IndexMetadata
import com.reposage.app.data.SearchPayload
import com.reposage.app.data.SearchResult

@Composable
fun SearchScreen(
    viewModel: SearchViewModel,
    modifier: Modifier = Modifier,
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    SearchScreenContent(
        uiState = uiState,
        onQuestionChanged = viewModel::onQuestionChanged,
        onAsk = viewModel::onAskClicked,
        onSearch = viewModel::onSearchClicked,
        onRetry = viewModel::onRetry,
        modifier = modifier,
    )
}

@Composable
fun SearchScreenContent(
    uiState: SearchUiState,
    onQuestionChanged: (String) -> Unit,
    onAsk: () -> Unit,
    onSearch: () -> Unit,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text(
            text = "RepoSage",
            style = MaterialTheme.typography.headlineMedium,
        )
        OutlinedTextField(
            value = uiState.draftQuestion,
            onValueChange = onQuestionChanged,
            modifier = Modifier
                .fillMaxWidth()
                .testTag("question-input"),
            label = { Text("Question") },
            minLines = 2,
            maxLines = 4,
            placeholder = { Text("Ask about the indexed repository") },
        )
        val requestInFlight = uiState.content is SearchContentState.Loading
        Row(
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Button(
                onClick = onAsk,
                enabled = !requestInFlight,
            ) {
                Text("Ask")
            }
            OutlinedButton(
                onClick = onSearch,
                enabled = !requestInFlight,
            ) {
                Text("Search code")
            }
        }

        when (val content = uiState.content) {
            SearchContentState.Initial -> InitialState()
            is SearchContentState.Loading -> LoadingState(
                submittedQuestion = content.submittedQuestion,
                mode = content.mode,
            )
            is SearchContentState.SearchResults -> ResultsState(content.payload)
            is SearchContentState.Answer -> AnswerState(content.payload)
            is SearchContentState.InsufficientEvidence -> InsufficientEvidenceState(content.payload)
            is SearchContentState.Empty -> EmptyState(
                submittedQuestion = content.submittedQuestion,
                metadata = content.metadata,
            )
            is SearchContentState.Error -> ErrorState(
                content = content,
                onRetry = onRetry,
            )
        }
    }
}

@Composable
private fun InitialState() {
    Text(
        text = "Ask for a grounded answer or search retrieved code.",
        style = MaterialTheme.typography.bodyMedium,
    )
}

@Composable
private fun LoadingState(
    submittedQuestion: String,
    mode: RequestMode,
) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        CircularProgressIndicator()
        Column {
            Text(
                text = when (mode) {
                    RequestMode.Ask -> "Generating answer"
                    RequestMode.SearchCode -> "Searching code"
                },
            )
            Text(
                text = submittedQuestion,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}

@Composable
private fun ResultsState(payload: SearchPayload) {
    SubmittedQuestion(payload.query)
    MetadataLine(payload.indexMetadata)
    Text(
        text = "Scores are retrieval ranking values, not confidence.",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    payload.results.forEachIndexed { index, result ->
        ResultItem(
            index = index + 1,
            result = result,
        )
    }
}

@Composable
private fun AnswerState(payload: AnswerPayload) {
    SubmittedQuestion(payload.query)
    AnswerDetails(payload = payload)
    Text(
        text = "Claims are grounded by cited source IDs. Citation validation does not prove semantic correctness.",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    var selectedSourceId by rememberSaveable(payload.query) {
        mutableStateOf<String?>(null)
    }
    payload.claims.forEachIndexed { index, claim ->
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            HorizontalDivider()
            Text(
                text = "${index + 1}. ${claim.text}",
                style = MaterialTheme.typography.bodyLarge,
            )
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.fillMaxWidth(),
            ) {
                claim.sourceIds.forEach { sourceId ->
                    val source = payload.sourceFor(sourceId)
                    TextButton(
                        onClick = { selectedSourceId = sourceId },
                        enabled = source != null,
                        modifier = Modifier.testTag("citation-$sourceId"),
                    ) {
                        Text(sourceId)
                    }
                }
            }
        }
    }
    payload.sourceFor(selectedSourceId.orEmpty())?.let { source ->
        SourceDetail(source = source)
    }
}

@Composable
private fun InsufficientEvidenceState(payload: AnswerPayload) {
    SubmittedQuestion(payload.query)
    AnswerDetails(payload = payload)
    Text(
        text = "Insufficient evidence in the retrieved source chunks to answer this question.",
        style = MaterialTheme.typography.titleMedium,
    )
    Text(
        text = "This is an abstention from the supplied evidence, not proof that the feature is absent.",
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

@Composable
private fun EmptyState(
    submittedQuestion: String,
    metadata: IndexMetadata,
) {
    SubmittedQuestion(submittedQuestion)
    MetadataLine(metadata)
    Text(
        text = "No matching source chunks were found in the current index.",
        style = MaterialTheme.typography.titleMedium,
    )
}

@Composable
private fun ErrorState(
    content: SearchContentState.Error,
    onRetry: () -> Unit,
) {
    if (content.submittedQuestion.isNotBlank()) {
        SubmittedQuestion(content.submittedQuestion)
    }
    Text(
        text = content.message,
        style = MaterialTheme.typography.titleMedium,
        color = MaterialTheme.colorScheme.error,
    )
    if (content.canRetry) {
        Button(onClick = onRetry) {
            Text("Retry")
        }
    }
}

@Composable
private fun AnswerDetails(payload: AnswerPayload) {
    val shortRevision = payload.indexMetadata.gitHead.take(12).ifBlank { "unknown" }
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(
            text = "Model ${payload.modelId}",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = "Revision $shortRevision | dirty: ${payload.indexMetadata.gitDirty} | ${payload.indexMetadata.filesIndexed} files | ${payload.indexMetadata.chunksIndexed} chunks",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        payload.latencyMs?.let { latencyMs ->
            Text(
                text = "Backend latency ${latencyMs} ms",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun SubmittedQuestion(question: String) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(
            text = "Submitted question",
            style = MaterialTheme.typography.labelLarge,
        )
        Text(
            text = question,
            style = MaterialTheme.typography.bodyLarge,
        )
    }
}

@Composable
private fun MetadataLine(metadata: IndexMetadata) {
    val shortRevision = metadata.gitHead.take(12).ifBlank { "unknown" }
    Text(
        text = "Revision $shortRevision | dirty: ${metadata.gitDirty} | ${metadata.filesIndexed} files | ${metadata.chunksIndexed} chunks",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

@Composable
private fun SourceDetail(source: AnswerSource) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .testTag("answer-source-detail"),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        HorizontalDivider()
        Text(
            text = "${source.sourceId}: ${source.path}:L${source.startLine}-L${source.endLine}",
            style = MaterialTheme.typography.titleSmall,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
        Text(
            text = source.citation,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        SelectionContainer {
            Text(
                text = source.text,
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState()),
                fontFamily = FontFamily.Monospace,
                style = MaterialTheme.typography.bodySmall,
                softWrap = false,
            )
        }
    }
}

@Composable
private fun ResultItem(
    index: Int,
    result: SearchResult,
) {
    var expanded by rememberSaveable(result.chunkId) {
        mutableStateOf(false)
    }

    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        HorizontalDivider()
        Text(
            text = "$index. ${result.path}:L${result.startLine}-L${result.endLine}",
            style = MaterialTheme.typography.titleSmall,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
        Text(
            text = result.citation,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        SelectionContainer {
            Text(
                text = result.text,
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState()),
                fontFamily = FontFamily.Monospace,
                style = MaterialTheme.typography.bodySmall,
                maxLines = if (expanded) Int.MAX_VALUE else COLLAPSED_CODE_LINES,
                overflow = TextOverflow.Ellipsis,
                softWrap = false,
            )
        }
        TextButton(onClick = { expanded = !expanded }) {
            Text(if (expanded) "Collapse code" else "Expand code")
        }
        Spacer(modifier = Modifier.height(4.dp))
    }
}

private const val COLLAPSED_CODE_LINES = 8
