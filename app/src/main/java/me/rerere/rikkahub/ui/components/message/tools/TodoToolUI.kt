package me.rerere.rikkahub.ui.components.message.tools

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import me.rerere.hugeicons.HugeIcons
import me.rerere.hugeicons.stroke.CheckList
import me.rerere.rikkahub.R
import me.rerere.rikkahub.data.ai.tools.TODO_TOOL_NAME

/**
 * rhPlanBar228: todo_write 的思考链渲染(文档8)——只渲染一行摘要。
 * 计划的当前状态由输入栏上方的 PlanBar 常驻展示;思考链里保留的是每次调用的
 * 变更历史(一次调用一条记录),点开走通用详情面板看原始 JSON 入参。
 */
object TodoToolUI : ToolUIRenderer {
    override val toolName: String = TODO_TOOL_NAME

    override fun icon(context: ToolUIContext) = HugeIcons.CheckList

    @Composable
    override fun title(context: ToolUIContext): String {
        val todos = remember(context.arguments) { parseTodoArguments(context.arguments) }
        val completed = todos.count { it.second == "completed" }
        // 标题形如「计划 (2/5)」(文档8)
        return stringResource(R.string.chat_message_todo_title) +
            " (" + completed + "/" + todos.size + ")"
    }

    override fun hasSummary(context: ToolUIContext): Boolean = true

    @Composable
    override fun Summary(context: ToolUIContext) {
        val todos = remember(context.arguments) { parseTodoArguments(context.arguments) }
        // 当前进行中的那一步;没有进行中的则取最后一个未完成的(与 PlanBar 同一回退)
        val current = todos.firstOrNull { it.second == "in_progress" }
            ?: todos.lastOrNull { it.second != "completed" }
        if (current != null) {
            Text(
                text = current.first,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

/**
 * rhPlanBar228: 从工具入参 JSON 解析清单(容错:整体失败返回空,单条失败跳过,
 * status 缺省按 pending)。与 TodoPlanCard.parseTodos 同规则,输入是 JsonElement。
 */
private fun parseTodoArguments(arguments: JsonElement): List<Pair<String, String>> {
    return runCatching {
        val root = arguments.jsonObject
        (root["todos"] as? JsonArray).orEmpty().mapNotNull { element ->
            runCatching {
                val obj = element.jsonObject
                val content = obj["content"]?.jsonPrimitive?.contentOrNull ?: return@runCatching null
                val status = obj["status"]?.jsonPrimitive?.contentOrNull ?: "pending"
                content to status
            }.getOrNull()
        }
    }.getOrDefault(emptyList())
}
