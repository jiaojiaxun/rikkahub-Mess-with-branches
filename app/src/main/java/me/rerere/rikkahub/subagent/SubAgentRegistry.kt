package me.rerere.rikkahub.subagent

import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import java.util.concurrent.ConcurrentHashMap

/**
 * 内存运行注册表（移植自 AAAelina，fork 适配：去掉 ToolNameSnapshot 依赖）。
 * runs 是 StateFlow 供 UI 收集；jobs 私有。LRU 上限 50，只逐出终态项。
 */
class SubAgentRegistry {

    private val _runs = MutableStateFlow<Map<String, SubAgentRun>>(emptyMap())
    val runs: StateFlow<Map<String, SubAgentRun>> = _runs

    private val activeJobs = ConcurrentHashMap<String, Job>()

    enum class Reservation { RESERVED, GLOBAL_CAP, ASSISTANT_CAP, DUPLICATE }

    fun reservePending(run: SubAgentRun, globalCap: Int, assistantCap: Int): Reservation {
        require(run.status == SubAgentStatus.PENDING)
        require(globalCap > 0 && assistantCap > 0)
        while (true) {
            val current = _runs.value
            if (run.id in current) return Reservation.DUPLICATE
            val active = current.values.filter { it.status == SubAgentStatus.PENDING || it.status == SubAgentStatus.RUNNING }
            if (active.size >= globalCap) return Reservation.GLOBAL_CAP
            if (active.count { it.parentAssistantId == run.parentAssistantId } >= assistantCap) return Reservation.ASSISTANT_CAP
            if (_runs.compareAndSet(current, pruneIfNeeded(current) + (run.id to run))) return Reservation.RESERVED
        }
    }

    fun terminalizeIfActive(id: String, status: SubAgentStatus, error: String?) {
        update(id) {
            if (it.status == SubAgentStatus.PENDING || it.status == SubAgentStatus.RUNNING)
                it.copy(status = status, error = error, finishedAtMs = System.currentTimeMillis())
            else it
        }
        activeJobs.remove(id)?.cancel()
    }

    fun update(id: String, transform: (SubAgentRun) -> SubAgentRun) {
        _runs.update { current ->
            val existing = current[id] ?: return@update current
            val next = transform(existing)
            if (existing.status !in setOf(SubAgentStatus.PENDING, SubAgentStatus.RUNNING) &&
                next.status in setOf(SubAgentStatus.PENDING, SubAgentStatus.RUNNING)) current
            else current + (id to next)
        }
    }

    fun setJob(id: String, job: Job) {
        activeJobs[id] = job
        val status = get(id)?.status
        if (status != SubAgentStatus.PENDING && status != SubAgentStatus.RUNNING) {
            activeJobs.remove(id, job)
            job.cancel()
        }
    }

    fun get(id: String): SubAgentRun? = _runs.value[id]

    fun getForAssistant(id: String, parentAssistantId: String): SubAgentRun? =
        _runs.value[id]?.takeIf { it.parentAssistantId == parentAssistantId }

    fun list(activeOnly: Boolean): List<SubAgentRun> {
        val all = _runs.value.values
        return if (activeOnly) all.filter { it.status == SubAgentStatus.RUNNING || it.status == SubAgentStatus.PENDING }
        else all.toList()
    }

    fun listForAssistant(parentAssistantId: String, activeOnly: Boolean): List<SubAgentRun> =
        list(activeOnly).filter { it.parentAssistantId == parentAssistantId }

    fun activeCountForAssistant(parentAssistantId: String): Int =
        _runs.value.values.count {
            it.parentAssistantId == parentAssistantId &&
                (it.status == SubAgentStatus.RUNNING || it.status == SubAgentStatus.PENDING)
        }

    fun globalActiveCount(): Int =
        _runs.value.values.count {
            it.status == SubAgentStatus.RUNNING || it.status == SubAgentStatus.PENDING
        }

    fun requestCancel(id: String): Boolean {
        val run = get(id) ?: return false
        if (run.status != SubAgentStatus.PENDING && run.status != SubAgentStatus.RUNNING) return false
        val job = activeJobs.remove(id)
        if (job != null) job.cancel()
        else terminalizeIfActive(id, SubAgentStatus.CANCELLED, "cancelled_before_start")
        return true
    }

    fun requestCancelForAssistant(id: String, parentAssistantId: String): Boolean {
        val run = getForAssistant(id, parentAssistantId) ?: return false
        if (run.status != SubAgentStatus.RUNNING && run.status != SubAgentStatus.PENDING) return false
        return requestCancel(id)
    }

    fun cancelAllForParent(parentChatId: String): Int {
        var count = 0
        val toCancel = _runs.value.values
            .filter { it.parentChatId == parentChatId && (it.status == SubAgentStatus.RUNNING || it.status == SubAgentStatus.PENDING) }
            .map { it.id }
        for (runId in toCancel) {
            if (requestCancel(runId)) count++
        }
        return count
    }

    fun cancelAllActive(): Int {
        var count = 0
        val toCancel = _runs.value.values
            .filter { it.status == SubAgentStatus.RUNNING || it.status == SubAgentStatus.PENDING }
            .map { it.id }
        for (runId in toCancel) {
            if (requestCancel(runId)) count++
        }
        return count
    }

    fun clearJob(id: String) {
        activeJobs.remove(id)
    }

    private fun pruneIfNeeded(current: Map<String, SubAgentRun>): Map<String, SubAgentRun> {
        if (current.size < SubAgentDefaults.REGISTRY_LRU_CAP) return current
        val terminalSorted = current.values
            .filter { it.status != SubAgentStatus.RUNNING && it.status != SubAgentStatus.PENDING }
            .sortedBy { it.finishedAtMs ?: it.startedAtMs }
        val toEvictId = terminalSorted.firstOrNull()?.id
        return if (toEvictId != null) current - toEvictId else current
    }
}
