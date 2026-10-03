package me.rerere.rikkahub.ui.pages.setting

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LargeFlexibleTopAppBar
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.launch
import me.rerere.hugeicons.HugeIcons
import me.rerere.hugeicons.stroke.Delete01
import me.rerere.hugeicons.stroke.Play
import me.rerere.rikkahub.data.cron.CronJobStore
import me.rerere.rikkahub.data.cron.ScheduledJobRunRecord
import me.rerere.rikkahub.data.model.CronJob
import me.rerere.rikkahub.data.model.CronParser
import me.rerere.rikkahub.ui.components.nav.BackButton
import me.rerere.rikkahub.ui.components.ui.CardGroup
import me.rerere.rikkahub.ui.theme.CustomColors
import org.koin.compose.koinInject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 定时任务管理页（fork 新增）。
 *
 * 背景：AI 可以通过 schedule_job 等工具自己建定时任务，但此前没有任何
 * 界面能查看、开关、删除或手动触发 —— 用户只能让 AI 列给他看。本页把
 * CronJobStore 的 jobsFlow/historyFlow 直接接进来，补上这个可见性缺口。
 */
@Composable
fun SettingScheduledJobsPage() {
    val store: CronJobStore = koinInject()
    val jobs by store.jobsFlow.collectAsStateWithLifecycle(initialValue = emptyList())
    val history by store.historyFlow.collectAsStateWithLifecycle(initialValue = emptyList())
    val scope = rememberCoroutineScope()
    val scrollBehavior = TopAppBarDefaults.exitUntilCollapsedScrollBehavior()
    var detailJob by remember { mutableStateOf<CronJob?>(null) }

    Scaffold(
        topBar = {
            LargeFlexibleTopAppBar(
                title = { Text("定时任务") },
                navigationIcon = { BackButton() },
                scrollBehavior = scrollBehavior,
                colors = CustomColors.topBarColors,
            )
        },
        modifier = Modifier.nestedScroll(scrollBehavior.nestedScrollConnection),
        containerColor = CustomColors.topBarColors.containerColor,
    ) { contentPadding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = contentPadding + PaddingValues(8.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            item("jobs") {
                CardGroup(
                    modifier = Modifier.padding(horizontal = 8.dp),
                    title = { Text("已创建的任务") },
                ) {
                    if (jobs.isEmpty()) {
                        item(
                            headlineContent = { Text("还没有定时任务") },
                            supportingContent = {
                                Text("在聊天里让 AI 设置定时任务，之后会出现在这里")
                            },
                        )
                    } else {
                        jobs.forEach { job ->
                            item(
                                onClick = { detailJob = job },
                                headlineContent = { Text(job.name) },
                                supportingContent = {
                                    Column {
                                        Text(job.cronExpression + "  ·  " + job.prompt.take(60))
                                        val next = job.nextRunAt
                                        if (next != null) {
                                            Text(
                                                text = "下次：" + formatTime(next),
                                                style = MaterialTheme.typography.labelSmall,
                                            )
                                        }
                                    }
                                },
                                trailingContent = {
                                    Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                                        Switch(
                                            checked = job.enabled,
                                            onCheckedChange = { checked ->
                                                scope.launch { store.upsert(job.copy(enabled = checked)) }
                                            },
                                        )
                                    }
                                },
                            )
                        }
                    }
                }
            }

            item("history") {
                CardGroup(
                    modifier = Modifier.padding(horizontal = 8.dp),
                    title = { Text("最近执行记录") },
                ) {
                    if (history.isEmpty()) {
                        item(
                            headlineContent = { Text("还没有执行记录") },
                        )
                    } else {
                        history.take(20).forEach { record ->
                            item(
                                headlineContent = { Text(record.jobName) },
                                supportingContent = { Text(recordSummary(record)) },
                            )
                        }
                    }
                }
            }
        }
    }

    detailJob?.let { job ->
        androidx.compose.material3.AlertDialog(
            onDismissRequest = { detailJob = null },
            title = { Text(job.name) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("cron：" + job.cronExpression)
                    Text("提示词：" + job.prompt)
                    val next = job.nextRunAt
                    if (next != null) Text("下次执行：" + formatTime(next))
                    val last = job.lastRunAt
                    if (last != null) Text("上次执行：" + formatTime(last))
                    if (!CronParser.isValid(job.cronExpression)) {
                        Text("cron 表达式无法解析，不会被调度", color = MaterialTheme.colorScheme.error)
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { detailJob = null }) { Text("关闭") }
            },
            dismissButton = {
                TextButton(onClick = {
                    scope.launch { store.delete(job.id) }
                    detailJob = null
                }) {
                    Text("删除", color = MaterialTheme.colorScheme.error)
                }
            },
        )
    }
}

private fun formatTime(millis: Long): String =
    SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()).format(Date(millis))

private fun recordSummary(record: ScheduledJobRunRecord): String {
    val outcome = when (record.outcome) {
        "success" -> "成功"
        "timeout" -> "超时"
        "failure" -> "失败"
        else -> record.outcome
    }
    val whenText = formatTime(record.startedAtMs)
    val err = record.error?.let { "（" + it.take(50) + "）" } ?: ""
    return whenText + "  ·  " + outcome + err
}
