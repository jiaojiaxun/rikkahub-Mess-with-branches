package me.rerere.rikkahub.ui.components.message

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import me.rerere.ai.ui.UIMessage
import me.rerere.ai.ui.UIMessagePart
import me.rerere.hugeicons.HugeIcons
import me.rerere.hugeicons.stroke.TaskDone01
import me.rerere.rikkahub.R
import me.rerere.rikkahub.data.ai.tools.TODO_TOOL_NAME
import me.rerere.rikkahub.utils.JsonInstant

/** rhPlanBar228: 计划条目(文档5.5,对外暴露给聊天页计划细条使用) */
data class TodoEntry(val content: String, val status: String)

/** rhPlanBar228: 完成态绿色(文档用 extendColors.green6,fork 侧硬编码等效色) */
internal val TodoPlanGreen = Color(0xFF43A047)

/**
 * rhPlanBar237: 从消息列表里取「当前计划」——倒序取最新的可解析 todo_write 调用(文档5.5)。
 * 不再要求 isExecuted: 模型一发出完整参数即显示(不必等整批工具执行完, 显示时机提前);
 * 流式半截 JSON 解析失败自动跳过并回落更早一次调用; 从未调用或不合法返回空(入口隐藏)。
 */
fun findActivePlan(messages: List<UIMessage>): List<TodoEntry> =
    messages.asReversed()
        .asSequence()
        .flatMap { message -> message.parts.asReversed().asSequence() }
        .filterIsInstance<UIMessagePart.Tool>()
        .filter { it.toolName == TODO_TOOL_NAME }
        .mapNotNull { part -> parseTodos(part.input).takeIf { it.isNotEmpty() } }
        .firstOrNull()
        .orEmpty()

/**
 * rhPlanBar228: 容错解析(文档5.5)——整体解析失败返回空列表;单条目失败跳过;
 * status 缺省按 pending。任何输入都不会让 UI 崩溃。
 */
private fun parseTodos(rawJson: String): List<TodoEntry> {
    return runCatching {
        val root = JsonInstant.parseToJsonElement(rawJson).jsonObject
        (root["todos"] as? JsonArray).orEmpty().mapNotNull { element ->
            runCatching {
                val obj = element.jsonObject
                val content = obj["content"]?.jsonPrimitive?.contentOrNull ?: return@runCatching null
                val status = obj["status"]?.jsonPrimitive?.contentOrNull ?: "pending"
                TodoEntry(content, status)
            }.getOrNull()
        }
    }.getOrDefault(emptyList())
}

/**
 * rhPlanBar228: 计划清单主体(文档5.6)——细条展开区与正文卡片共用。
 * showHeader=false 时不渲染标题行(细条场景:状态与进度已在上方行里,不重复渲染)。
 */
@Composable
fun TodoPlanContent(
    todos: List<TodoEntry>,
    modifier: Modifier = Modifier,
    showHeader: Boolean = true,
) {
    if (todos.isEmpty()) return
    val completed = todos.count { it.status == "completed" }
    Column(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 14.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        if (showHeader) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(
                    text = stringResource(R.string.chat_message_todo_title),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
                Text(
                    text = stringResource(R.string.chat_message_todo_count_hint, completed, todos.size),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        todos.forEach { item ->
            TodoRow(item)
        }
    }
}

/**
 * rhPlanBar228: 单条计划三态渲染(文档5.6)——completed 绿勾+删除线+55%透明度;
 * in_progress 主色实心圆点;pending 灰色描边空心圆。颜色/透明度带 220ms 过渡。
 */
@Composable
private fun TodoRow(item: TodoEntry) {
    val isDone = item.status == "completed"
    val isActive = item.status == "in_progress"
    val contentAlpha by animateFloatAsState(
        targetValue = if (isDone) 0.55f else 1f,
        animationSpec = tween(220),
        label = "todoRowAlpha",
    )
    val markColor by animateColorAsState(
        targetValue = when {
            isDone -> TodoPlanGreen
            isActive -> MaterialTheme.colorScheme.primary
            else -> MaterialTheme.colorScheme.outlineVariant
        },
        animationSpec = tween(220),
        label = "todoRowMark",
    )
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        when {
            isDone -> Icon(
                imageVector = HugeIcons.TaskDone01,
                contentDescription = null,
                modifier = Modifier.size(14.dp),
                tint = markColor,
            )

            isActive -> Box(
                modifier = Modifier.size(14.dp),
                contentAlignment = Alignment.Center,
            ) {
                Box(
                    modifier = Modifier
                        .size(8.dp)
                        .background(color = markColor, shape = CircleShape),
                )
            }

            else -> Box(
                modifier = Modifier.size(14.dp),
                contentAlignment = Alignment.Center,
            ) {
                Box(
                    modifier = Modifier
                        .size(8.dp)
                        .border(width = 1.5.dp, color = markColor, shape = CircleShape),
                )
            }
        }
        Text(
            text = item.content,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = contentAlpha),
            textDecoration = if (isDone) TextDecoration.LineThrough else null,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
    }
}
