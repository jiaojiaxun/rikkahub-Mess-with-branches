package me.rerere.rikkahub.ui.pages.chat

import me.rerere.ai.core.MessageRole
import me.rerere.ai.ui.UIMessage
import me.rerere.rikkahub.data.ai.ContextCompactionPresentation
import me.rerere.rikkahub.data.model.MessageNode
import kotlin.uuid.Uuid

/**
 * A display-only grouping of assistant nodes separated by automatic context compression.
 *
 * Generation still retains every node independently, which keeps tool replay and provider
 * history correct. The UI renders the cards and continuation text as one assistant message.
 */
internal data class AutoCompactionMessageGroup(
    val nodes: List<MessageNode>,
) {
    init {
        require(nodes.isNotEmpty())
    }

    val id: Uuid = nodes.first().id
    val terminalNode: MessageNode = nodes.last()

    // rhLosslessStream241: displayMessage 改为惰性求值。
    // groupAutomaticCompactionMessages() 每次 messageNodes 变化都会重建全部分组实例,
    // 原实现让每个分组在构造瞬间就 copy 一次 UIMessage 并 flatMap 深拷贝全部 parts;
    // 流式期间每 token 一次 => 全程 O(n^2) 的对象分配与列表深拷贝。
    // 只有被 LazyColumn 组合到的可见分组才读取 displayMessage, 故改为 lazy:
    // 不可见的历史分组零构造; 可见分组每次都是新实例, 求值时读到当前最新文本。
    val displayMessage: UIMessage by lazy(LazyThreadSafetyMode.NONE) {
        terminalNode.currentMessage.copy(
            parts = nodes.flatMap { it.currentMessage.parts },
            annotations = nodes.flatMap { it.currentMessage.annotations },
            createdAt = nodes.first().currentMessage.createdAt,
        )
    }
}

internal fun List<MessageNode>.groupAutomaticCompactionMessages(): List<AutoCompactionMessageGroup> {
    if (isEmpty()) return emptyList()

    val groups = mutableListOf<AutoCompactionMessageGroup>()
    var index = 0
    while (index < size) {
        val groupedNodes = mutableListOf(this[index])
        while (
            groupedNodes.last().currentMessage.role == MessageRole.ASSISTANT &&
            ContextCompactionPresentation.hasDisplayTool(groupedNodes.last().currentMessage) &&
            index + 1 < size &&
            this[index + 1].currentMessage.role == MessageRole.ASSISTANT
        ) {
            index++
            groupedNodes += this[index]
        }
        groups += AutoCompactionMessageGroup(groupedNodes)
        index++
    }
    return groups
}
