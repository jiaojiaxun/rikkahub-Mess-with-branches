package me.rerere.rikkahub.ui.components.message

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import me.rerere.hugeicons.HugeIcons
import me.rerere.hugeicons.stroke.ArrowDown01
import me.rerere.hugeicons.stroke.CheckList
import me.rerere.hugeicons.stroke.TaskDone01
import me.rerere.rikkahub.R

/**
 * rhPlanBar228: 计划细条(移植自 YuiHub,文档5.6)——常驻在输入栏正上方,收起时一行高度。
 * 收起态一行显示「进行中的步骤 + 进度计数 + 旋转箭头」,底部贴 2dp 进度条;
 * 点击整行向下展开完整清单,再点收起。无计划时整条隐藏。
 */
@Composable
fun PlanBar(
    todos: List<TodoEntry>,
    modifier: Modifier = Modifier,
    alpha: Float = 1f,
) {
    // 无计划:整条消失(文档5.6 守卫)
    if (todos.isEmpty()) return

    val completed = todos.count { it.status == "completed" }
    val total = todos.size
    val allDone = completed == total
    // 当前进行中的那一步;没有进行中的则取最后一个未完成的(文档5.6 回退逻辑)
    val current = todos.firstOrNull { it.status == "in_progress" }
        ?: todos.lastOrNull { it.status != "completed" }

    // 展开状态非持久化:旋转屏幕/进程重建后重置为收起(文档9 已知取舍)
    var expanded by remember { mutableStateOf(false) }
    val arrowRotation by animateFloatAsState(
        targetValue = if (expanded) 180f else 0f,
        animationSpec = tween(260),
        label = "planBarArrow",
    )

    Surface(
        modifier = modifier
            .fillMaxWidth()
            .graphicsLayer { this.alpha = alpha },
        shape = MaterialTheme.shapes.largeIncreased, // rhTopBarBubbles300-plan
        color = MaterialTheme.colorScheme.surfaceContainerLow,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)),
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { expanded = !expanded }
                    .padding(horizontal = 14.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Icon(
                    imageVector = if (allDone) HugeIcons.TaskDone01 else HugeIcons.CheckList,
                    contentDescription = null,
                    modifier = Modifier.size(17.dp),
                    tint = if (allDone) TodoPlanGreen else MaterialTheme.colorScheme.primary,
                )
                Text(
                    text = if (allDone) {
                        stringResource(R.string.chat_message_todo_all_done)
                    } else {
                        current?.content ?: stringResource(R.string.chat_message_todo_title)
                    },
                    style = MaterialTheme.typography.bodySmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f),
                )
                Text(
                    text = "$completed/$total",
                    style = MaterialTheme.typography.labelMedium,
                    color = if (allDone) TodoPlanGreen else MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Icon(
                    imageVector = HugeIcons.ArrowDown01,
                    contentDescription = stringResource(
                        if (expanded) R.string.chat_message_todo_collapse else R.string.plan_bar_expand
                    ),
                    modifier = Modifier
                        .size(16.dp)
                        .graphicsLayer { rotationZ = arrowRotation },
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            // 2dp 细线贴在下沿;展开时同时充当与清单的分隔(文档5.6)
            LinearProgressIndicator(
                progress = { completed.toFloat() / total },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(2.dp),
                color = if (allDone) TodoPlanGreen else MaterialTheme.colorScheme.primary,
                trackColor = MaterialTheme.colorScheme.surfaceContainerHighest,
                drawStopIndicator = {},
                gapSize = 0.dp,
            )

            AnimatedVisibility(
                visible = expanded,
                enter = expandVertically(expandFrom = Alignment.Top) + fadeIn(tween(160)),
                exit = shrinkVertically(shrinkTowards = Alignment.Top) + fadeOut(tween(120)),
            ) {
                // 只渲染条目本身:状态与进度已在上方行里,不再重复渲染标题行(文档5.6)
                TodoPlanContent(todos = todos, showHeader = false)
            }
        }
    }
}
