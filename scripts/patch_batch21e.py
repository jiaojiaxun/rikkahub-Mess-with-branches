from pathlib import Path

ROOT = Path.cwd()
PATH = "app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatVM.kt"

text = (ROOT / PATH).read_text(encoding="utf-8")


def fail(msg):
    print(f"::error file={PATH}::batch21e {msg[:1400]}")
    raise SystemExit(1)


if "pendingMessages" in text:
    print("batch21e v3: already applied")
    raise SystemExit(0)

# --- 0) imports：Mutex/withLock（first/launch 原文件已 import） ---
ANCHOR_IMPORT = "import kotlinx.coroutines.launch\n"
IMPORT_NEW = "import kotlinx.coroutines.launch\nimport kotlinx.coroutines.sync.Mutex\nimport kotlinx.coroutines.sync.withLock\n"
if text.count(ANCHOR_IMPORT) != 1:
    fail(f"import anchor count={text.count(ANCHOR_IMPORT)} != 1")
text = text.replace(ANCHOR_IMPORT, IMPORT_NEW, 1)

# --- 1) 排队字段 + drain（插在 inputState 后） ---
# v3（对抗性审查 P0-1/P0-3）：
#  a) generationDoneFlow 是全局流（发出 conversationId），必须按本会话过滤——
#     v2 不过滤，任一会话完成都会误触发本会话发送（跨会话误触发）。
#  b) 不再用 stateIn 副本 conversationJob.value 判断（异步传播有竞态），
#     改为统一入队 + drain 时读服务端真相流 getGenerationJobStateFlow(id)
#     等空闲（上游 ResearchTools.kt / SubAgentEngine.kt 同款模式）。
#  c) 队列上限 20，超出丢弃（防连发内存膨胀）。
#  d) stopGeneration 时清空队列（停止后不被 done 事件自动放行）。
ANCHOR1 = """    // 聊天输入状态 - 保存在 ViewModel 中避免 TransactionTooLargeException
    val inputState = ChatInputState()
"""

INSERT1 = """    // 聊天输入状态 - 保存在 ViewModel 中避免 TransactionTooLargeException
    val inputState = ChatInputState()

    // 任务N4 v3：消息排队发送——触发生成的消息统一入队，单一 pump 串行放行，
    // 避免生成期间并发 sendMessage。队列仅存内存（VM 生命周期）。
    private val pendingMessages = java.util.concurrent.ConcurrentLinkedQueue<List<me.rerere.ai.ui.UIMessagePart>>()
    private val pendingMessageCountState = androidx.compose.runtime.mutableStateOf(0)
    val pendingMessageCount: androidx.compose.runtime.State<Int> = pendingMessageCountState
    private val pendingPumpMutex = Mutex()

    init {
        // 本会话生成完成 → 尝试放行下一条（generationDoneFlow 是全局流，
        // 发出的是 conversationId，必须过滤，否则跨会话误触发）
        viewModelScope.launch {
            chatService.generationDoneFlow.collect { doneConversationId ->
                if (doneConversationId == _conversationId) {
                    drainOnePendingMessage()
                }
            }
        }
    }

    /** 放行一条排队消息：等本会话空闲后发送（读服务端真相流，无 stateIn 竞态）。 */
    private fun drainOnePendingMessage() {
        viewModelScope.launch {
            pendingPumpMutex.withLock {
                if (pendingMessages.isEmpty()) return@withLock
                chatService.getGenerationJobStateFlow(_conversationId).first { it == null }
                val next = pendingMessages.poll() ?: return@withLock
                pendingMessageCountState.value = pendingMessages.size
                chatService.sendMessage(_conversationId, next, true)
            }
        }
    }
"""

if text.count(ANCHOR1) != 1:
    fail(f"anchor1 count={text.count(ANCHOR1)} != 1")
text = text.replace(ANCHOR1, INSERT1, 1)

# --- 2) handleMessageSend：触发生成的消息统一走排队通道 ---
ANCHOR2 = """        fun handleMessageSend(content: List<UIMessagePart>,answer: Boolean = true) {
        if (content.isEmptyInputMessage()) return
        chatService.sendMessage(_conversationId, content, answer)
    }
"""

NEW2 = """        fun handleMessageSend(content: List<UIMessagePart>,answer: Boolean = true) {
        if (content.isEmptyInputMessage()) return
        // answer=false 的插入型消息不排队直接执行；触发生成的统一入队，
        // 由 drainOnePendingMessage 串行放行（cap 20，超出丢弃防内存膨胀）
        if (!answer) {
            chatService.sendMessage(_conversationId, content, false)
            return
        }
        if (pendingMessages.size >= 20) return
        pendingMessages.add(content)
        pendingMessageCountState.value = pendingMessages.size
        drainOnePendingMessage()
    }

    /** 丢弃全部排队消息（用户在排队时点停止生成）。 */
    fun clearPendingMessages() {
        pendingMessages.clear()
        pendingMessageCountState.value = 0
    }
"""

if text.count(ANCHOR2) != 1:
    fail(f"anchor2 count={text.count(ANCHOR2)} != 1 (handleMessageSend)")
text = text.replace(ANCHOR2, NEW2, 1)

# --- 3) stopGeneration：停止时清空队列 ---
ANCHOR3 = """    fun stopGeneration() {
        viewModelScope.launch {
            chatService.stopGeneration(_conversationId)
        }
    }
"""

NEW3 = """    fun stopGeneration() {
        // 任务N4：停止生成同时丢弃排队消息，避免停止后队列被 done 事件自动放行
        clearPendingMessages()
        viewModelScope.launch {
            chatService.stopGeneration(_conversationId)
        }
    }
"""

if text.count(ANCHOR3) != 1:
    fail(f"anchor3 count={text.count(ANCHOR3)} != 1 (stopGeneration)")
text = text.replace(ANCHOR3, NEW3, 1)

(ROOT / PATH).write_text(text, encoding="utf-8")
print("batch21e v3: queueing with conversationId filter + service-truth idle wait + stop-clear")
