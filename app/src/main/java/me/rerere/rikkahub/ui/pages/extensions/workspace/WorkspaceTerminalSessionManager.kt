package me.rerere.rikkahub.ui.pages.extensions.workspace

import android.content.Context
import android.util.Log
import com.termux.terminal.TerminalSession
import com.termux.terminal.TerminalTransport
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.getAndUpdate
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import me.rerere.rikkahub.AppScope
import me.rerere.rikkahub.data.db.entity.WorkspaceEntity
import me.rerere.rikkahub.data.repository.WorkspaceRepository
import java.util.concurrent.atomic.AtomicLong

/**
 * Owns workspace terminal sessions independently from the terminal page lifecycle.
 *
 * A page only attaches a [com.termux.view.TerminalView] to the selected tab, so navigating
 * away keeps every shell and its screen buffer alive. A session is finished only when its tab
 * is explicitly closed or the shell exits by itself.
 *
 * 本地工作区走 libtermux.so 提供的伪终端(rhLocalTerminal360), SSH 工作区走 SshTerminalTransport;
 * 两条路径共用同一套标签页状态机, 页面只负责把 TerminalView 挂到选中的会话上。
 */
class WorkspaceTerminalSessionManager internal constructor(
    context: Context,
    private val appScope: AppScope,
    private val workspaceRepository: WorkspaceRepository,
    // rhLocalTerminal359: 本地工作区的终端启动参数由 ProotShellRunner 提供
    private val workspaceManager: me.rerere.workspace.WorkspaceManager,
) {
    private val appContext = context.applicationContext
    private val workspaceStates = MutableStateFlow<Map<String, WorkspaceTerminalTabsState>>(emptyMap())
    private val nextTabId = AtomicLong(1)
    private val creationJobs = mutableMapOf<String, Job>()

    internal fun observeWorkspace(root: String): Flow<WorkspaceTerminalTabsState> =
        workspaceStates
            .map { states -> states[root] ?: WorkspaceTerminalTabsState() }
            .distinctUntilChanged()

    internal fun ensureSession(workspace: WorkspaceEntity) {
        launchCreateTab(workspace = workspace, onlyIfEmpty = true)
    }

    internal fun createTab(workspace: WorkspaceEntity) {
        launchCreateTab(workspace = workspace, onlyIfEmpty = false)
    }

    internal fun selectTab(root: String, tabId: Long) {
        updateState(root) { state ->
            if (state.tabs.none { it.id == tabId }) state else state.copy(selectedTabId = tabId)
        }
    }

    internal fun closeTab(root: String, tabId: Long) {
        var closedTab: WorkspaceTerminalTab? = null
        updateState(root) { state ->
            val closedIndex = state.tabs.indexOfFirst { it.id == tabId }
            if (closedIndex < 0) return@updateState state

            closedTab = state.tabs[closedIndex]
            val remainingTabs = state.tabs.filterNot { it.id == tabId }
            val selectedTabId = if (state.selectedTabId == tabId) {
                remainingTabs.getOrNull(closedIndex)?.id
                    ?: remainingTabs.getOrNull(closedIndex - 1)?.id
            } else {
                state.selectedTabId
            }
            state.copy(tabs = remainingTabs, selectedTabId = selectedTabId)
        }

        // 先从 observable state 移除再结束, 否则 finish 回调可能把 tab 又塞回 UI。
        closedTab?.let { tab ->
            tab.client.terminalView = null
            tab.session.finishIfRunning()
        }
    }

    /** 删除工作区前调用: 结束该工作区全部会话。 */
    internal suspend fun closeWorkspace(root: String) = withContext(Dispatchers.Main.immediate) {
        creationJobs[root]?.cancelAndJoin()
        val state = workspaceStates.getAndUpdate { states -> states - root }[root]
            ?: return@withContext
        state.tabs.forEach { tab ->
            tab.client.terminalView = null
            tab.session.finishIfRunning()
        }
    }

    private fun launchCreateTab(workspace: WorkspaceEntity, onlyIfEmpty: Boolean) {
        val root = workspace.root
        if (root in creationJobs) return

        lateinit var job: Job
        job = appScope.launch(start = CoroutineStart.LAZY) {
            try {
                createTab(workspace = workspace, onlyIfEmpty = onlyIfEmpty)
            } finally {
                creationJobs.remove(root, job)
            }
        }
        creationJobs[root] = job
        job.start()
    }

    private suspend fun createTab(workspace: WorkspaceEntity, onlyIfEmpty: Boolean) = withContext(
        Dispatchers.Main.immediate
    ) {
        val root = workspace.root
        val initialState = currentState(root)
        if (initialState.isCreating || (onlyIfEmpty && initialState.tabs.isNotEmpty())) {
            return@withContext
        }
        updateState(root) { it.copy(isCreating = true) }

        val tabId = nextTabId.getAndIncrement()
        val tabNumber = currentState(root).nextTabNumber
        val client = WorkspaceTerminalSessionClient(
            context = appContext,
            onTitleUpdated = { title -> updateTitle(root, tabId, title) },
            onFinished = { markFinished(root = root, tabId = tabId) },
        )
        var failure: String? = null
        val session = runCatching {
            createWorkspaceTerminalSession(
                transport = terminalTransport(workspace),
                root = root,
                client = client,
            )
        }.onFailure { error ->
            Log.e(TAG, "Failed to create terminal for workspace $root", error)
            failure = error.message ?: error.toString()
        }.getOrNull()

        if (session == null) {
            updateState(root) { it.copy(isCreating = false, lastError = failure) }
            return@withContext
        }

        val tab = WorkspaceTerminalTab(
            id = tabId,
            number = tabNumber,
            session = session,
            client = client,
        )
        updateState(root) { state ->
            state.copy(
                tabs = state.tabs + tab,
                selectedTabId = tab.id,
                isCreating = false,
                nextTabNumber = tabNumber + 1,
                lastError = null,
            )
        }
    }

    private fun terminalTransport(workspace: WorkspaceEntity): TerminalTransport {
        if (!workspace.isSsh()) {
            // rhLocalTerminal360: 本地工作区走 libtermux.so 的伪终端。
            // PRoot 参数、bind mount 与 env 白名单都由 ProotShellRunner 组装, 与命令执行完全一致。
            val launch = workspaceManager.terminalLaunch(
                root = workspace.root,
                shellCompatibilityMode = workspace.shellCompatibilityMode,
            ) ?: error("本地终端不可用：rootfs 未安装、农场缺失或兼容模式已开启，请先在工作区详情里安装 Rootfs")
            return com.termux.terminal.LocalPtyTransport(
                launch.executable,
                launch.cwd,
                launch.args.toTypedArray(),
                launch.env.toTypedArray(),
            )
        }
        val settings = workspace.sshSettings() ?: error("SSH workspace config is missing: ${workspace.id}")
        return SshTerminalTransport(address = "${settings.username}@${settings.host}:${settings.port}") { columns, rows ->
            workspaceRepository.openSshShell(workspace, columns, rows)
        }
    }

    private fun updateTitle(root: String, tabId: Long, title: String?) {
        val normalizedTitle = title?.trim()?.takeIf { it.isNotEmpty() }
        workspaceStates.update { states ->
            val state = states[root] ?: return@update states
            if (state.tabs.none { it.id == tabId }) return@update states
            states + (root to state.copy(
                tabs = state.tabs.map { tab ->
                    if (tab.id == tabId) tab.copy(title = normalizedTitle) else tab
                },
            ))
        }
    }

    private fun markFinished(root: String, tabId: Long) {
        workspaceStates.update { states ->
            val state = states[root] ?: return@update states
            if (state.tabs.none { it.id == tabId }) return@update states
            states + (root to state.copy(
                tabs = state.tabs.map { tab ->
                    if (tab.id == tabId) tab.copy(finished = true) else tab
                },
            ))
        }
    }

    private fun currentState(root: String): WorkspaceTerminalTabsState =
        workspaceStates.value[root] ?: WorkspaceTerminalTabsState()

    private inline fun updateState(
        root: String,
        transform: (WorkspaceTerminalTabsState) -> WorkspaceTerminalTabsState,
    ) {
        workspaceStates.update { states ->
            states + (root to transform(states[root] ?: WorkspaceTerminalTabsState()))
        }
    }

    private companion object {
        const val TAG = "WorkspaceTerminalManager"
    }
}

internal data class WorkspaceTerminalTabsState(
    val tabs: List<WorkspaceTerminalTab> = emptyList(),
    val selectedTabId: Long? = null,
    val isCreating: Boolean = false,
    val nextTabNumber: Int = 1,
    /** rhLocalTerminal362: 最近一次建会话失败的原因, 供终端页空态展示 */
    val lastError: String? = null,
)

internal data class WorkspaceTerminalTab(
    val id: Long,
    val number: Int,
    val session: TerminalSession,
    val client: WorkspaceTerminalSessionClient,
    val title: String? = null,
    val finished: Boolean = false,
)
