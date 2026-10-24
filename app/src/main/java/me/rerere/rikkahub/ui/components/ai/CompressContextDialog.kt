package me.rerere.rikkahub.ui.components.ai

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.Switch
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Job
import me.rerere.rikkahub.R
import me.rerere.rikkahub.ui.components.ui.OutlinedNumberInput
import me.rerere.rikkahub.ui.components.ui.RabbitLoadingIndicator
import kotlin.uuid.Uuid

@Composable
fun CompressContextDialog(
    defaultTargetTokens: Int,
    onDismiss: () -> Unit,
    onConfirm: (additionalPrompt: String, targetTokens: Int, keepRecentMessages: Int) -> Job,
    // Conversation being compressed; used to show the compression model's live reply.
    conversationId: Uuid? = null,
    // rh-batch8:truncate-only - optional "delete instead of summarise" action. Left null the
    // toggle is hidden, so an existing call site keeps compiling unchanged.
    onTruncate: ((keepRecentMessages: Int) -> Job)? = null,
) {
    var additionalPrompt by remember { mutableStateOf("") }
    var targetTokensK by remember(defaultTargetTokens) { mutableStateOf("") }
        var keepRecentMessages by remember { mutableStateOf(32) }
    // rh-batch8:truncate-only - when on, the confirm button deletes instead of summarising.
    var truncateOnly by remember { mutableStateOf(false) }
    var currentJob by remember { mutableStateOf<Job?>(null) }
    val isLoading = currentJob?.isActive == true

    // Monitor job completion
    LaunchedEffect(currentJob) {
        currentJob?.join()
        if (currentJob?.isCompleted == true && currentJob?.isCancelled == false) {
            onDismiss()
        }
        currentJob = null
    }

    AlertDialog(
        onDismissRequest = {
            if (!isLoading) {
                onDismiss()
            }
        },
        title = {
            Text(stringResource(R.string.chat_page_compress_context_title))
        },
        text = {
            Column(
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                if (isLoading) {
                    // Loading state
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.Center,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        RabbitLoadingIndicator(
                            modifier = Modifier.size(32.dp)
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(stringResource(R.string.chat_page_compressing))
                    }
                    CompactionStreamPreview(
                        conversationId = conversationId,
                        modifier = Modifier.fillMaxWidth(),
                    )
                                } else {
                    // rh-batch8:truncate-only - choose between the original model-backed summary
                    // and a purely local "keep only the last N messages" cleanup.
                    if (onTruncate != null) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "只保留最近 N 条（不总结，直接删除旧消息）",
                                style = MaterialTheme.typography.bodyMedium,
                                modifier = Modifier.weight(1f)
                            )
                            Switch(
                                checked = truncateOnly,
                                onCheckedChange = { truncateOnly = it }
                            )
                        }
                    }

                    if (truncateOnly) {
                        OutlinedNumberInput(
                            value = keepRecentMessages,
                            onValueChange = { keepRecentMessages = it },
                            label = "保留最近多少条消息",
                            modifier = Modifier.fillMaxWidth(),
                        )
                        Text(
                            text = "将直接删除更早的消息，不调用任何模型、不产生费用，且无法撤销。",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.error
                        )
                    } else {
                    Text(stringResource(R.string.chat_page_compress_context_desc))

                    // Token size selector
                    Text(
                        text = stringResource(R.string.chat_page_compress_target_tokens),
                        style = MaterialTheme.typography.labelMedium
                    )
                    OutlinedTextField(
                        value = targetTokensK,
                        onValueChange = { value ->
                            targetTokensK = value.filter(Char::isDigit).take(7)
                        },
                        singleLine = true,
                        suffix = { Text("k") },
                        placeholder = { Text("${(defaultTargetTokens + 999) / 1_000}") },
                        keyboardOptions = KeyboardOptions(
                            keyboardType = KeyboardType.Number,
                        ),
                        modifier = Modifier
                            .fillMaxWidth()
                            .onFocusChanged { focusState ->
                                if (!focusState.isFocused) {
                                    targetTokensK = targetTokensK.toIntOrNull()
                                        ?.coerceIn(1, Int.MAX_VALUE / 1_000)
                                        ?.toString()
                                        .orEmpty()
                                }
                            },
                    )

                    // Keep recent messages input
                    OutlinedNumberInput(
                        value = keepRecentMessages,
                        onValueChange = { keepRecentMessages = it },
                        label = stringResource(R.string.chat_page_compress_keep_recent),
                        modifier = Modifier.fillMaxWidth(),
                    )

                    // Additional context input
                    OutlinedTextField(
                        value = additionalPrompt,
                        onValueChange = { additionalPrompt = it },
                        label = {
                            Text(stringResource(R.string.chat_page_compress_additional_prompt))
                        },
                        placeholder = {
                            Text(stringResource(R.string.chat_page_compress_additional_prompt_hint))
                        },
                        modifier = Modifier.fillMaxWidth(),
                        maxLines = 4,
                    )

                                        // Warning text
                    Text(
                        text = stringResource(R.string.chat_page_compress_warning),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error
                    )
                    }
                }
            }
        },
        confirmButton = {
            if (isLoading) {
                TextButton(onClick = {
                    currentJob?.cancel()
                    currentJob = null
                }) {
                    Text(stringResource(R.string.cancel))
                }
            } else {
                TextButton(onClick = {
                    val targetTokens = targetTokensK.toIntOrNull()
                        ?.coerceIn(1, Int.MAX_VALUE / 1_000)
                        ?.toLong()
                        ?.times(1_000L)
                        ?.coerceAtMost(Int.MAX_VALUE.toLong())
                        ?.toInt()
                        ?: defaultTargetTokens
                    currentJob = if (truncateOnly) {
                        // rh-batch8:truncate-only - no compression model is contacted here.
                        onTruncate?.invoke(keepRecentMessages)
                    } else {
                        onConfirm(additionalPrompt, targetTokens, keepRecentMessages)
                    }
                }) {
                    Text(stringResource(R.string.confirm))
                }
            }
        },
        dismissButton = {
            if (!isLoading) {
                TextButton(onClick = onDismiss) {
                    Text(stringResource(R.string.cancel))
                }
            }
        }
    )
}
