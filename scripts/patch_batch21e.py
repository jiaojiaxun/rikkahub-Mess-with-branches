import re
from pathlib import Path

ROOT = Path.cwd()
PATH = "app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatVM.kt"

text = (ROOT / PATH).read_text(encoding="utf-8")


def fail(msg):
    print(f"::error file={PATH}::batch21e {msg[:1400]}")
    raise SystemExit(1)


if "pendingMessages" in text:
    print("batch21e v2: already applied")
    raise SystemExit(0)

# --- 1) 排队字段 + drain 逻辑：插在 inputState 声明后 ---
# v2 修复：init 块直接用 chatService.generationDoneFlow（主构造参数，任何 init
# 前可用），不用类内后置声明的 generationDoneFlow 属性——那会在本 init 执行时
# 还是 null（Kotlin 属性按声明顺序初始化），v1 会 UninitializedPropertyAccess。
# pendingMessageCount 直接声明为 MutableState（免到处 unchecked cast）。
ANCHOR1 = """    // 聊天输入状态 - 保存在 ViewModel 中避免 TransactionTooLargeException
    val inputState = ChatInputState()
"""

INSERT1 = """    // 聊天输入状态 - 保存在 ViewModel 中避免 TransactionTooLargeException
    val inputState = ChatInputState()

    // 任务N4：消息排队发送（对齐上游 2.5.6 行为）——生成进行中时，新消息先入队，
    // 当前生成结束后自动按序发送。队列仅存内存（VM 生命周期）。
    private val pendingMessages = java.util.concurrent.ConcurrentLinkedQueue<List<me.rerere.ai.ui.UIMessagePart>>()
    private val pendingMessageCountState = androidx.compose.runtime.mutableStateOf(0)
    val pendingMessageCount: androidx.compose.runtime.State<Int> = pendingMessageCountState

    init {
        // 生成完成事件：队列非空则弹出发送下一条。
        // 用 chatService.generationDoneFlow（构造参数，此刻已可用）而非
        // 类内后置声明的 generationDoneFlow 属性（按声明顺序届时尚未初始化）。
        viewModelScope.launch {
            chatService.generationDoneFlow.collect {
                if (pendingMessages.isNotEmpty()) {
                    val next = pendingMessages.poll() ?: return@collect
                    pendingMessageCountState.value = pendingMessages.size
                    chatService.sendMessage(_conversationId, next, true)
                }
            }
        }
    }
"""

if text.count(ANCHOR1) != 1:
    fail(f"anchor1 count={text.count(ANCHOR1)} != 1")
text = text.replace(ANCHOR1, INSERT1, 1)

# --- 2) handleMessageSend 改为排队感知 ---
ANCHOR2 = """        fun handleMessageSend(content: List<UIMessagePart>,answer: Boolean = true) {
        if (content.isEmptyInputMessage()) return
        chatService.sendMessage(_conversationId, content, answer)
    }
"""

NEW2 = """        fun handleMessageSend(content: List<UIMessagePart>,answer: Boolean = true) {
        if (content.isEmptyInputMessage()) return
        // 生成中：入队等待（仅触发生成的消息需要排队；answer=false 的插入直接执行）
        if (answer && conversationJob.value?.isActive == true) {
            pendingMessages.add(content)
            pendingMessageCountState.value = pendingMessages.size
            return
        }
        chatService.sendMessage(_conversationId, content, answer)
    }

    /** 丢弃全部排队消息（用户在排队时点停止/清空）。 */
    fun clearPendingMessages() {
        pendingMessages.clear()
        pendingMessageCountState.value = 0
    }
"""

if text.count(ANCHOR2) != 1:
    fail(f"anchor2 count={text.count(ANCHOR2)} != 1 (handleMessageSend)")
text = text.replace(ANCHOR2, NEW2, 1)

(ROOT / PATH).write_text(text, encoding="utf-8")
print("batch21e v2: message queueing + auto-drain (init-order-safe)")
