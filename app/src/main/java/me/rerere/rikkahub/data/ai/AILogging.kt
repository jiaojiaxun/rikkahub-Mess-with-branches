package me.rerere.rikkahub.data.ai

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch
import me.rerere.rikkahub.AppScope
import me.rerere.rikkahub.data.datastore.AiLogLevel
import me.rerere.rikkahub.data.datastore.SettingsStore
import me.rerere.ai.provider.ProviderSetting
import kotlin.uuid.Uuid
import me.rerere.ai.provider.TextGenerationParams
import me.rerere.ai.ui.UIMessage

sealed class AILogging {
    data class Generation(
        val params: TextGenerationParams,
        val messages: List<UIMessage>,
        val providerSetting: ProviderSetting,
        val stream: Boolean,
    ) : AILogging()
}

private const val MAX_LOGS = 32
private const val PROVIDER_LAST_USED_MIN_INTERVAL_MS = 30_000L // rhProviderTidy

class AILoggingManager(
    private val settingsStore: SettingsStore,
    private val appScope: AppScope,
) {
    private val logs = MutableStateFlow<List<AILogging>>(emptyList())
    private val logLevel = MutableStateFlow(settingsStore.settingsFlow.value.aiLogLevel)

    init {
        appScope.launch {
            settingsStore.settingsFlow
                .map { it.aiLogLevel }
                .collectLatest { logLevel.value = it }
        }
    }

    fun getLogs(): StateFlow<List<AILogging>> = logs

    fun getLogLevel(): StateFlow<AiLogLevel> = logLevel

    suspend fun setLogLevel(level: AiLogLevel) {
        settingsStore.update { it.copy(aiLogLevel = level) }
    }

    fun addLog(log: AILogging) {
        if (logLevel.value == AiLogLevel.OFF) return
        logs.value = logs.value + log
        if (logs.value.size > MAX_LOGS) {
            logs.value = logs.value.drop(1)
        }
    }

    fun clearLogs() {
        logs.value = emptyList()
    }

    /** rhProviderTidy: 记录供应商最后一次被调用成功的时间(30 秒节流,防 DataStore 写放大)。 */
    fun recordProviderUsed(providerId: Uuid) {
        appScope.launch {
            settingsStore.update { settings ->
                val now = System.currentTimeMillis()
                val last = settings.providerLastUsedAt[providerId] ?: 0L
                if (now - last < PROVIDER_LAST_USED_MIN_INTERVAL_MS) settings
                else settings.copy(
                    providerLastUsedAt = settings.providerLastUsedAt + (providerId to now)
                )
            }
        }
    }
}
