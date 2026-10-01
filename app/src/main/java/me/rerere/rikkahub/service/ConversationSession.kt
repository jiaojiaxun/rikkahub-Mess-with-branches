package me.rerere.rikkahub.service

import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.getAndUpdate
import kotlinx.coroutines.launch
import me.rerere.rikkahub.data.model.Conversation
import java.util.concurrent.atomic.AtomicInteger
import kotlin.uuid.Uuid

private const val TAG = "ConversationSession"
private const val IDLE_TIMEOUT_MS = 5_000L

class ConversationSession(
    val id: Uuid,
    initial: Conversation,
    private val scope: CoroutineScope,
    private val onIdle: (Uuid) -> Unit,
    private val onGenerationFinished: (Uuid, Throwable?) -> Unit = { _, _ -> },
) {
    // 会话状态
    private val _state = MutableStateFlow(initial)
    val state: StateFlow<Conversation> = _state.asStateFlow()
    private val initializationMutex = Mutex()
    private val metadataMutex = Mutex()
    @Volatile
    private var initialized = false
    val messageQueue = MessageQueue()

    // 页面切换和 SSE 重连只加载一次；活跃 session 的内存状态始终优先。
    suspend fun initialize(load: suspend () -> Conversation) {
        initializationMutex.withLock {
            if (initialized) return
            val conversation = load()
            synchronized(this) {
                // 加载挂起期间可能已经通过保存或编辑写入了更新的状态。
                if (!initialized) updateConversation(conversation)
            }
        }
    }

    @Synchronized
    fun updateConversation(conversation: Conversation) {
        require(conversation.id == id)
        _state.value = conversation
        initialized = true
    }

    // 元数据先应用到最新内存状态；落库只更新对应列，不能用旧消息快照覆盖流式输出。
    internal suspend fun updateMetadata(
        update: (Conversation) -> Conversation,
        persist: suspend (Conversation) -> Unit,
    ) {
        metadataMutex.withLock {
            val updated = synchronized(this) {
                update(state.value).also(::updateConversation)
            }
            persist(updated)
        }
    }

    // 失败和取消也必须保存已收到的内容，且保存完成前不能释放生成任务。
    suspend fun finishGeneration(save: suspend (Conversation) -> Unit): Conversation =
        withContext(NonCancellable) {
            val current = state.value
            val conversation = current.copy(
                messageNodes = current.messageNodes.map { node ->
                    node.copy(messages = node.messages.map { it.finishReasoning() })
                },
                updateAt = Instant.now(),
            )
            updateConversation(conversation)
            save(conversation)
            conversation
        }

    // 从队列取出到写入会话历史之间，附件仍需作为有效引用保留。
    @Volatile
    var submittingMessage: QueuedMessage? = null
        internal set

    // 原子引用计数
    private val refCount = AtomicInteger(0)

    // 处理状态（如 OCR 识别中）
    val processingStatus = MutableStateFlow<String?>(null)

    // 生成任务（内聚在 session 中）
    private val _generationJob = MutableStateFlow<Job?>(null)
    val generationJob: StateFlow<Job?> = _generationJob.asStateFlow()
    val isGenerating: Boolean get() = _generationJob.value?.isActive == true
    val isInUse: Boolean get() = refCount.get() > 0 || isGenerating

    // 空闲检查任务
    private var idleCheckJob: Job? = null

    fun acquire(): Int = refCount.incrementAndGet().also {
        cancelIdleCheck()
        Log.d(TAG, "acquire $id (refs=$it)")
    }

    fun release(): Int = refCount.decrementAndGet().also {
        Log.d(TAG, "release $id (refs=$it)")
        if (it <= 0) scheduleIdleCheck()
    }

    // 作用域 API - 短请求（REST）
    inline fun <T> withRef(block: () -> T): T {
        acquire()
        try {
            return block()
        } finally {
            release()
        }
    }

    // 作用域 API - 长连接（SSE、挂起函数）
    suspend inline fun <T> withRefSuspend(block: () -> T): T {
        acquire()
        try {
            return block()
        } finally {
            release()
        }
    }

    fun setJob(job: Job?) {
        // Atomic swap so two concurrent setJob callers can't race-write a stale job.
        // The previous code (cancel() then assign) had a window where two writers could
        // each read the prior value, A cancels old, B reads old (already cancelled,
        // no-op), A writes newA, B writes newB → A's job is untracked but still running;
        // getJob() returns B; stopGeneration only cancels B; A leaks until completion.
        val previous = _generationJob.getAndUpdate { job }
        previous?.cancel()
        // Identity-checked completion handler: only null the StateFlow if the value is
        // STILL the same job we just set. Without this an out-of-order setJob(B) →
        // A.invokeOnCompletion → clobber-B race could null out the live job.
        job?.invokeOnCompletion {
            _generationJob.compareAndSet(job, null)
            if (refCount.get() <= 0) {
                scheduleIdleCheck()
            }
        }
    }

    fun getJob(): Job? = _generationJob.value

    private fun scheduleIdleCheck() {
        idleCheckJob?.cancel()
        idleCheckJob = scope.launch {
            delay(IDLE_TIMEOUT_MS)
            if (refCount.get() <= 0 && !isGenerating) {
                onIdle(id)
            }
        }
    }

    private fun cancelIdleCheck() {
        idleCheckJob?.cancel()
        idleCheckJob = null
    }

    fun cleanup() {
        // Use getAndUpdate (same as setJob) so cleanup() is consistent with the atomic
        // swap used elsewhere. Direct .value = null would bypass the CAS and could
        // theoretically race with a concurrent setJob that's running post-removal
        // (e.g., a coroutine that had already acquired a session reference before
        // dropSession removed it from the map). In practice the risk is tiny because
        // cleanup() is only called after removal, but correctness still matters.
        val job = _generationJob.getAndUpdate { null }
        job?.cancel()
        idleCheckJob?.cancel()
        idleCheckJob = null
    }
}
