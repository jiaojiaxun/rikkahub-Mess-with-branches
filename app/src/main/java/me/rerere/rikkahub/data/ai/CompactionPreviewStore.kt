package me.rerere.rikkahub.data.ai

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlin.uuid.Uuid

/**
 * Live text of in-flight context-compaction requests, so the UI can show what the
 * compression model is writing instead of a bare spinner.
 *
 * Keyed by conversation, then by request: a compaction can run several map requests in
 * parallel, each streaming into its own slot. Entries are removed when a request ends
 * (success, failure or cancellation), so an empty map means nothing is compressing.
 */
object CompactionPreviewStore {
    private val _previews = MutableStateFlow<Map<Uuid, Map<String, String>>>(emptyMap())
    val previews: StateFlow<Map<Uuid, Map<String, String>>> = _previews.asStateFlow()

    fun update(conversationId: Uuid, streamId: String, text: String) {
        _previews.update { all ->
            all + (conversationId to (all[conversationId].orEmpty() + (streamId to text)))
        }
    }

    fun clear(conversationId: Uuid, streamId: String) {
        _previews.update { all ->
            val rest = all[conversationId].orEmpty() - streamId
            if (rest.isEmpty()) all - conversationId else all + (conversationId to rest)
        }
    }
}
