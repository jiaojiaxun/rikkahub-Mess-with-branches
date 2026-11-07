package me.rerere.rikkahub.ui.pages.setting

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.LargeFlexibleTopAppBar
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
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.launch
import me.rerere.rikkahub.data.cron.CronJobStore
import me.rerere.rikkahub.data.cron.ScheduledJobRunRecord
import me.rerere.rikkahub.data.model.CronJob
import me.rerere.rikkahub.data.model.CronParser
import me.rerere.rikkahub.service.CronJobScheduler
import me.rerere.rikkahub.ui.components.nav.BackButton
import me.rerere.rikkahub.ui.components.ui.CardGroup
import me.rerere.rikkahub.ui.theme.CustomColors
import me.rerere.rikkahub.utils.plus
import org.koin.compose.koinInject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import me.rerere.hugeicons.HugeIcons
import me.rerere.hugeicons.stroke.Add01
import androidx.compose.foundation.layout.Spacer // rhCronBeautify
import androidx.compose.foundation.layout.width // rhCronBeautify
import androidx.compose.material3.Surface // rhCronBeautify

/**
 * 定时任务管理页（fork 新增）。
 *
 * 背景：AI 可以通过 schedule_job 等工具自己建定时任务，但此前没有任何
 * 界面能查看、开关、删除或手动触发 —— 用户只能让 AI 列给他看。本页把
 * CronJobStore 的 jobsFlow/historyFlow 直接接进来，补上这个可见性缺口。
 *
 * 注：`me.rerere.rikkahub.utils.plus` 是 fork 为 PaddingValues 提供的扩展，
 * 不加这个 import 会在 `contentPadding + PaddingValues(...)` 处编译失败
 * （#121 的教训）。
 */
@Composable
fun SettingScheduledJobsPage() {
    val store: CronJobStore = koinInject()
    val scheduler: CronJobScheduler = koinInject()
    val jobs by store.jobsFlow.collectAsStateWithLifecycle(initialValue = emptyList())
    val history by store.historyFlow.collectAsStateWithLifecycle(initialValue = emptyList())
    val scope = rememberCoroutineScope()
    val scrollBehavior = TopAppBarDefaults.exitUntilCollapsedScrollBehavior()
    var detailJob by remember { mutableStateOf<CronJob?>(null) }
    var showCreateDialog by remember { mutableStateOf(false) } // rhCronManual
    var editJob by remember { mutableStateOf<CronJob?>(null) } // rhCronManual

    Scaffold(
        topBar = {
            LargeFlexibleTopAppBar(
                title = { Text("定时任务") },
                actions = { // rhCronManual
                    IconButton(onClick = { showCreateDialog = true }) {
                        Icon(HugeIcons.Add01, contentDescription = "新建任务")
                    }
                },
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
                                        Text(describeCron(job.cronExpression) + "  ·  " + job.prompt.take(60))
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
                                    Switch(
                                        checked = job.enabled,
                                        onCheckedChange = { checked ->
                                            scope.launch {
                                                val updated = job.copy(enabled = checked)
                                                store.upsert(updated)
                                                if (checked) {
                                                    scheduler.schedule(updated)
                                                } else {
                                                    scheduler.cancel(job.id)
                                                }
                                            }
                                        },
                                    )
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
        AlertDialog(
            onDismissRequest = { detailJob = null },
            title = { Text(job.name) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("cron：" + job.cronExpression + "（" + describeCron(job.cronExpression) + "）")
                    Text("提示词：" + job.prompt)
                    val next = job.nextRunAt
                    if (next != null) Text("下次执行：" + formatTime(next))
                    val last = job.lastRunAt
                    if (last != null) Text("上次执行：" + formatTime(last))
                    if (!CronParser.isValid(job.cronExpression)) {
                        Text(
                            text = "cron 表达式无法解析，不会被调度",
                            color = MaterialTheme.colorScheme.error,
                        )
                    }
                    Text(
                        text = "立即执行会在后台触发一次，不等结果",
                        style = MaterialTheme.typography.labelSmall,
                    )
                }
            },
            confirmButton = {
                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    TextButton(onClick = { // rhCronManual
                        editJob = job
                        detailJob = null
                    }) {
                        Text("编辑")
                    }
                    TextButton(onClick = {
                        scheduler.triggerNow(job.id)
                        detailJob = null
                    }) {
                        Text("立即执行")
                    }
                    TextButton(onClick = {
                        scope.launch { store.delete(job.id) }
                        scheduler.cancel(job.id)
                        detailJob = null
                    }) {
                        Text("删除", color = MaterialTheme.colorScheme.error)
                    }
                }
            },
            dismissButton = {
                TextButton(onClick = { detailJob = null }) { Text("关闭") }
            },
        )
    }
    if (showCreateDialog || editJob != null) { // rhCronManual
        val editing = editJob
        var jobName by remember { mutableStateOf(editing?.name ?: "") }
        var cronExpr by remember { mutableStateOf(editing?.cronExpression ?: "0 9 * * *") }
        var jobPrompt by remember { mutableStateOf(editing?.prompt ?: "") }
        var jobEnabled by remember { mutableStateOf(editing?.enabled ?: true) }
        val cronValid = CronParser.isValid(cronExpr)
        AlertDialog(
            onDismissRequest = {
                showCreateDialog = false
                editJob = null
            },
            title = { Text(if (editing != null) "编辑任务" else "新建任务") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = jobName,
                        onValueChange = { jobName = it },
                        label = { Text("任务名称") },
                        singleLine = true,
                    )
                    OutlinedTextField(
                        value = cronExpr,
                        onValueChange = { cronExpr = it },
                        label = { Text("Cron 表达式") },
                        supportingText = {
                            Text(
                                text = if (cronValid) "格式正确" else "格式错误，应为：分 时 日 月 周",
                                color = if (cronValid) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
                            )
                        },
                        singleLine = true,
                    )
                    
                    // rhCronBeautify: cron preset chips
                    Text("常用示例：", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        listOf("0 9 * * *" to "每天 9:00", "0 * * * *" to "每小时", "0 9 * * 1" to "每周一 9:00", "*/30 * * * *" to "每 30 分钟").forEach { (cron, label) ->
                            Surface(
                                onClick = { cronExpr = cron },
                                shape = MaterialTheme.shapes.small,
                                color = MaterialTheme.colorScheme.secondaryContainer,
                            ) {
                                Text(
                                    text = label,
                                    style = MaterialTheme.typography.labelSmall,
                                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                                )
                            }
                        }
                    }
                    OutlinedTextField(
                        value = jobPrompt,
                        onValueChange = { jobPrompt = it },
                        label = { Text("提示词") },
                        minLines = 3,
                    )
                    Row(
                        verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text("启用")
                        Switch(checked = jobEnabled, onCheckedChange = { jobEnabled = it })
                    }
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        scope.launch {
                            val job = (editing ?: CronJob(
                                id = java.util.UUID.randomUUID().toString(),
                                name = jobName,
                                prompt = jobPrompt,
                                cronExpression = cronExpr,
                            )).copy(
                                name = jobName,
                                prompt = jobPrompt,
                                cronExpression = cronExpr,
                                enabled = jobEnabled,
                            )
                            store.upsert(job)
                            if (jobEnabled) scheduler.schedule(job) else scheduler.cancel(job.id)
                        }
                        showCreateDialog = false
                        editJob = null
                    },
                    enabled = jobName.isNotBlank() && cronValid,
                ) { Text("保存") }
            },
            dismissButton = {
                TextButton(onClick = {
                    showCreateDialog = false
                    editJob = null
                }) { Text("取消") }
            },
        )
    }
}

// rhCronDesc: cron 表达式 → 中文描述
private fun describeCron(expr: String): String {
    val parts = expr.trim().split(Regex("\\s+"))
    if (parts.size != 5) return expr
    val (min, hour, day, month, week) = parts
    fun num(s: String): Int? = s.toIntOrNull()
    fun pad2(n: Int): String = n.toString().padStart(2, '0')
    return when {
        min.startsWith("*/") -> "每 " + min.removePrefix("*/") + " 分钟"
        min == "*" -> "每分钟"
        hour == "*" -> "每小时第 " + min + " 分钟"
        week != "*" -> {
            val dayName = when (week) {
                "0", "7" -> "日"
                "1" -> "一"
                "2" -> "二"
                "3" -> "三"
                "4" -> "四"
                "5" -> "五"
                "6" -> "六"
                else -> week
            }
            "每周" + dayName + " " + (num(hour)?.let { pad2(it) } ?: hour) + ":" + (num(min)?.let { pad2(it) } ?: min)
        }
        day != "*" -> "每月 " + day + " 号 " + (num(hour)?.let { pad2(it) } ?: hour) + ":" + (num(min)?.let { pad2(it) } ?: min)
        else -> "每天 " + (num(hour)?.let { pad2(it) } ?: hour) + ":" + (num(min)?.let { pad2(it) } ?: min)
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
