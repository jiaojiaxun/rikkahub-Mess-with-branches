package me.rerere.rikkahub.ui.pages.stats

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import me.rerere.ai.provider.Model
import me.rerere.rikkahub.data.db.dao.ConversationDAO
import me.rerere.rikkahub.data.db.dao.MessageNodeDAO
import me.rerere.rikkahub.data.db.dao.UsageSummaryRow
import me.rerere.rikkahub.data.db.dao.getMessageCountPerDay
import me.rerere.rikkahub.data.db.dao.getTokenStats
import me.rerere.rikkahub.data.db.dao.getUsageSummary
import me.rerere.rikkahub.data.db.entity.ConversationEntity
import me.rerere.rikkahub.data.datastore.Settings
import me.rerere.rikkahub.data.datastore.SettingsStore
import me.rerere.rikkahub.data.model.ModelNameNormalizer
import java.time.DayOfWeek
import java.time.LocalDate
import java.time.YearMonth
import java.time.temporal.TemporalAdjusters

data class AppStats(
    val isLoading: Boolean = true,
    val totalConversations: Int = 0,
    val totalMessages: Int = 0,
    val totalPromptTokens: Long = 0L,
    val totalCompletionTokens: Long = 0L,
    val totalCachedTokens: Long = 0L,
    val conversationsPerDay: Map<LocalDate, Int> = emptyMap(),
    val launchCount: Int = 0,
    val progress: UsageSummaryProgress = UsageSummaryProgress(),
    val models: List<UsageModelSummary> = emptyList(),
    val providers: List<UsageProviderSummary> = emptyList(),
    val conversations: List<UsageConversationSummary> = emptyList(),
    val days: List<UsageDaySummary> = emptyList(),
    val months: List<UsageMonthSummary> = emptyList(),
    val years: List<UsageYearSummary> = emptyList(),
    val error: String? = null,
) {
    val totalTokens: Long get() = totalPromptTokens + totalCompletionTokens
}

enum class UsageSummaryStage {
    PREPARING,
    LOADING_CONVERSATIONS,
    LOADING_USAGE,
    AGGREGATING_MODELS,
    AGGREGATING_DATES,
    FINALIZING,
    COMPLETED,
    FAILED,
}

data class UsageSummaryProgress(
    val stage: UsageSummaryStage = UsageSummaryStage.PREPARING,
    val fraction: Float = 0f,
    val detail: String = "准备计算使用总结",
)

data class UsageModelSummary(
    val modelName: String,
    val providerName: String,
    val messageCount: Int,
    val promptTokens: Long,
    val completionTokens: Long,
    val cachedTokens: Long,
) {
    val totalTokens: Long get() = promptTokens + completionTokens
}

data class UsageProviderSummary(
    val providerName: String,
    val modelCount: Int,
    val messageCount: Int,
    val promptTokens: Long,
    val completionTokens: Long,
    val cachedTokens: Long,
) {
    val totalTokens: Long get() = promptTokens + completionTokens
}

data class UsageConversationSummary(
    val conversationId: String,
    val title: String,
    val messageCount: Int,
    val promptTokens: Long,
    val completionTokens: Long,
    val cachedTokens: Long,
) {
    val totalTokens: Long get() = promptTokens + completionTokens
}

data class UsageDaySummary(
    val day: LocalDate,
    val messageCount: Int,
    val promptTokens: Long,
    val completionTokens: Long,
    val cachedTokens: Long,
) {
    val totalTokens: Long get() = promptTokens + completionTokens
}

data class UsageMonthSummary(
    val month: YearMonth,
    val messageCount: Int,
    val promptTokens: Long,
    val completionTokens: Long,
    val cachedTokens: Long,
) {
    val totalTokens: Long get() = promptTokens + completionTokens
}

data class UsageYearSummary(
    val year: Int,
    val messageCount: Int,
    val promptTokens: Long,
    val completionTokens: Long,
    val cachedTokens: Long,
) {
    val totalTokens: Long get() = promptTokens + completionTokens
}

class StatsVM(
    private val conversationDAO: ConversationDAO,
    private val messageNodeDAO: MessageNodeDAO,
    private val settingsStore: SettingsStore,
) : ViewModel() {

    private val _stats = MutableStateFlow(AppStats())
    val stats = _stats.asStateFlow()

    init {
        viewModelScope.launch { loadStats() }
    }

    private suspend fun loadStats() {
        try {
            publishProgress(UsageSummaryStage.PREPARING, 0.02f, "准备数据库统计")
            val today = LocalDate.now()
            val startDate = today
                .with(TemporalAdjusters.previousOrSame(DayOfWeek.SUNDAY))
                .minusWeeks(52)
                .toString()

            publishProgress(UsageSummaryStage.LOADING_CONVERSATIONS, 0.12f, "读取会话索引")
            val conversations = withContext(Dispatchers.IO) { conversationDAO.getAll().first() }
            val conversationById = conversations.associateBy { it.id }

            publishProgress(UsageSummaryStage.LOADING_USAGE, 0.30f, "在 SQLite 中汇总消息 usage")
            val (conversationsPerDay, tokenStats, usageRows) = withContext(Dispatchers.IO) {
                val daily = messageNodeDAO.getMessageCountPerDay(startDate)
                    .mapNotNull { entry ->
                        runCatching { LocalDate.parse(entry.day) to entry.count }.getOrNull()
                    }
                    .toMap()
                Triple(daily, messageNodeDAO.getTokenStats(), messageNodeDAO.getUsageSummary())
            }

            publishProgress(
                UsageSummaryStage.AGGREGATING_MODELS,
                0.56f,
                "按模型与服务商归类 ${usageRows.size} 个聚合分组",
            )
            val settings = settingsStore.settingsFlow.value
            val grouped = withContext(Dispatchers.Default) {
                aggregateUsage(
                    rows = usageRows,
                    conversations = conversationById,
                    settings = settings,
                )
            }

            publishProgress(UsageSummaryStage.AGGREGATING_DATES, 0.78f, "按年、月、日整理 Token 趋势")
            publishProgress(UsageSummaryStage.FINALIZING, 0.92f, "整理展示数据")
            val launchCount = settings.launchCount
            _stats.value = AppStats(
                isLoading = false,
                totalConversations = conversations.size,
                totalMessages = tokenStats.totalMessages,
                totalPromptTokens = tokenStats.promptTokens,
                totalCompletionTokens = tokenStats.completionTokens,
                totalCachedTokens = tokenStats.cachedTokens,
                conversationsPerDay = conversationsPerDay,
                launchCount = launchCount,
                progress = UsageSummaryProgress(
                    UsageSummaryStage.COMPLETED,
                    1f,
                    "使用总结计算完成：${usageRows.size} 个 usage 分组",
                ),
                models = grouped.models,
                providers = grouped.providers,
                conversations = grouped.conversations,
                days = grouped.days,
                months = grouped.months,
                years = grouped.years,
            )
        } catch (error: Throwable) {
            _stats.value = _stats.value.copy(
                isLoading = false,
                error = error.message ?: "统计失败",
                progress = UsageSummaryProgress(
                    UsageSummaryStage.FAILED,
                    _stats.value.progress.fraction,
                    "使用总结计算失败：${error.message ?: "未知错误"}",
                ),
            )
        }
    }

    private fun publishProgress(stage: UsageSummaryStage, fraction: Float, detail: String) {
        _stats.value = _stats.value.copy(
            isLoading = stage != UsageSummaryStage.COMPLETED && stage != UsageSummaryStage.FAILED,
            progress = UsageSummaryProgress(stage, fraction.coerceIn(0f, 1f), detail),
        )
    }
}

internal data class AggregatedUsage(
    val models: List<UsageModelSummary>,
    val providers: List<UsageProviderSummary>,
    val conversations: List<UsageConversationSummary>,
    val days: List<UsageDaySummary>,
    val months: List<UsageMonthSummary>,
    val years: List<UsageYearSummary>,
)

private class UsageAccumulator {
    var modelName: String = "未知模型"
    var providerName: String = "未知服务商"
    var conversationTitle: String = "未命名对话"
    var messageCount: Int = 0
    var promptTokens: Long = 0L
    var completionTokens: Long = 0L
    var cachedTokens: Long = 0L

    fun add(row: UsageSummaryRow) {
        messageCount += row.messageCount
        promptTokens += row.promptTokens
        completionTokens += row.completionTokens
        cachedTokens += row.cachedTokens
    }
}

internal fun aggregateUsage(
    rows: List<UsageSummaryRow>,
    conversations: Map<String, ConversationEntity>,
    settings: Settings,
): AggregatedUsage {
    val modelLookup = buildMap<String, Pair<Model, String>> {
        settings.providers.forEach { provider ->
            provider.models.forEach { model ->
                put(model.id.toString(), model to provider.name)
            }
        }
    }
    val modelGroups = linkedMapOf<String, UsageAccumulator>()
    val providerGroups = linkedMapOf<String, UsageAccumulator>()
    val conversationGroups = linkedMapOf<String, UsageAccumulator>()
    val dayGroups = linkedMapOf<LocalDate, UsageAccumulator>()
    val monthGroups = linkedMapOf<YearMonth, UsageAccumulator>()
    val yearGroups = linkedMapOf<Int, UsageAccumulator>()

    rows.forEach { row ->
        val modelEntry = row.modelId?.let(modelLookup::get)
        val model = modelEntry?.first
        val providerName = modelEntry?.second?.takeIf { it.isNotBlank() } ?: "未知服务商"
        val displayName = model?.displayName?.takeIf { it.isNotBlank() }
            ?: model?.modelId?.takeIf { it.isNotBlank() }
            ?: "未知模型"
        val normalizedRowModelId = ModelNameNormalizer.key(row.modelId.orEmpty())
        val modelKey = if (model == null) {
            "unknown:${normalizedRowModelId.ifBlank { "model" }}"
        } else {
            ModelNameNormalizer.key(model.modelId.takeIf { it.isNotBlank() } ?: displayName)
                .ifBlank { "unknown-model" }
        }
        val conversationTitle = conversations[row.conversationId]?.title
            ?.takeIf { it.isNotBlank() }
            ?: "对话 ${row.conversationId.take(8)}"
        val day = runCatching { LocalDate.parse(row.day) }.getOrNull() ?: return@forEach
        val month = YearMonth.from(day)

        modelGroups.getOrPut(modelKey) {
            UsageAccumulator().apply {
                modelName = displayName
                this.providerName = providerName
            }
        }.add(row)
        providerGroups.getOrPut(providerName) { UsageAccumulator().apply { this.providerName = providerName } }
            .add(row)
        conversationGroups.getOrPut(row.conversationId) {
            UsageAccumulator().apply { this.conversationTitle = conversationTitle }
        }.add(row)
        dayGroups.getOrPut(day) { UsageAccumulator() }.add(row)
        monthGroups.getOrPut(month) { UsageAccumulator() }.add(row)
        yearGroups.getOrPut(day.year) { UsageAccumulator() }.add(row)
    }

    fun UsageAccumulator.toModelSummary() = UsageModelSummary(
        modelName = modelName,
        providerName = providerName,
        messageCount = messageCount,
        promptTokens = promptTokens,
        completionTokens = completionTokens,
        cachedTokens = cachedTokens,
    )

    fun UsageAccumulator.toProviderSummary(providerName: String, modelCount: Int) = UsageProviderSummary(
        providerName = providerName,
        modelCount = modelCount,
        messageCount = messageCount,
        promptTokens = promptTokens,
        completionTokens = completionTokens,
        cachedTokens = cachedTokens,
    )

    return AggregatedUsage(
        models = modelGroups.values
            .map(UsageAccumulator::toModelSummary)
            .sortedByDescending { it.totalTokens },
        providers = providerGroups.map { (provider, bucket) ->
            val modelCount = modelGroups.values.count { it.providerName == provider }
            bucket.toProviderSummary(provider, modelCount)
        }.sortedByDescending { it.totalTokens },
        conversations = conversationGroups.map { (id, bucket) ->
            UsageConversationSummary(
                conversationId = id,
                title = bucket.conversationTitle,
                messageCount = bucket.messageCount,
                promptTokens = bucket.promptTokens,
                completionTokens = bucket.completionTokens,
                cachedTokens = bucket.cachedTokens,
            )
        }.sortedByDescending { it.totalTokens },
        days = dayGroups.map { (day, bucket) ->
            UsageDaySummary(day, bucket.messageCount, bucket.promptTokens, bucket.completionTokens, bucket.cachedTokens)
        }.sortedByDescending { it.day },
        months = monthGroups.map { (month, bucket) ->
            UsageMonthSummary(month, bucket.messageCount, bucket.promptTokens, bucket.completionTokens, bucket.cachedTokens)
        }.sortedByDescending { it.month },
        years = yearGroups.map { (year, bucket) ->
            UsageYearSummary(year, bucket.messageCount, bucket.promptTokens, bucket.completionTokens, bucket.cachedTokens)
        }.sortedByDescending { it.year },
    )
}
