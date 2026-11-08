#!/usr/bin/env python3
# rhRemote355p: 终端多标签（P1 最后一项）
# 上游 WorkspaceTerminalSessionManager 裁剪版：去掉本地 rootfs 准备与 terminalLaunch
# （fork 未搬本地终端），只保留 SSH 分支；会话按 workspace.root 存活，离开页面不杀。
# 落地：新 Manager.kt + AppModule 注册 + 整文件重写 WorkspaceTerminalPage（TabRow/per-tab view）。
# 同文件冲突：Page 由 355c 写入, sort -V 下 355c < 355p → 本脚本覆盖为多标签版 ✓
import os

DIAG = "ci_diag_batch355p_terminal_tabs.txt"
ROOT = os.environ.get("GITHUB_WORKSPACE", os.getcwd())


def read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def write(p, t):
    d = os.path.dirname(p)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(p, "w", encoding="utf-8") as f:
        f.write(t)


MANAGER = r'''package me.rerere.rikkahub.ui.pages.extensions.workspace

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
 * 与上游的差异: fork 没有本地终端实现(LocalPtyTransport/terminalLaunch 未搬), 这里只保留
 * SSH 分支, 也不做 rootfs 准备(SSH 恒就绪)。
 */
class WorkspaceTerminalSessionManager internal constructor(
    context: Context,
    private val appScope: AppScope,
    private val workspaceRepository: WorkspaceRepository,
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
        val session = runCatching {
            createWorkspaceTerminalSession(
                transport = terminalTransport(workspace),
                root = root,
                client = client,
            )
        }.onFailure { error ->
            Log.e(TAG, "Failed to create terminal for workspace $root", error)
        }.getOrNull()

        if (session == null) {
            updateState(root) { it.copy(isCreating = false) }
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
            )
        }
    }

    private fun terminalTransport(workspace: WorkspaceEntity): TerminalTransport {
        check(workspace.isSsh()) { "Interactive terminal is only available for SSH workspaces" }
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
)

internal data class WorkspaceTerminalTab(
    val id: Long,
    val number: Int,
    val session: TerminalSession,
    val client: WorkspaceTerminalSessionClient,
    val title: String? = null,
    val finished: Boolean = false,
)
'''

PAGE = r'''package me.rerere.rikkahub.ui.pages.extensions.workspace

import android.graphics.Typeface
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imeAnimationTarget
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import com.termux.view.TerminalView
import me.rerere.hugeicons.HugeIcons
import me.rerere.hugeicons.stroke.Add01
import me.rerere.rikkahub.R
import me.rerere.rikkahub.data.db.entity.WorkspaceEntity
import me.rerere.rikkahub.data.repository.WorkspaceRepository
import me.rerere.rikkahub.ui.components.nav.BackButton
import me.rerere.rikkahub.ui.theme.CustomColors
import org.koin.compose.koinInject

/** 多标签终端页: 会话由 [WorkspaceTerminalSessionManager] 持有, 本页只把 TerminalView 挂到选中标签 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun WorkspaceTerminalPage(id: String) {
    val context = LocalContext.current
    val repository: WorkspaceRepository = koinInject()
    val manager: WorkspaceTerminalSessionManager = koinInject()
    var workspace by remember(id) { mutableStateOf<WorkspaceEntity?>(null) }
    var tabsState by remember(id) { mutableStateOf(WorkspaceTerminalTabsState()) }
    var controlDown by remember(id) { mutableStateOf(false) }
    var altDown by remember(id) { mutableStateOf(false) }
    val viewClient = remember(id) { WorkspaceTerminalViewClient(context) }
    viewClient.controlDown = controlDown
    viewClient.altDown = altDown

    LaunchedEffect(id) {
        val ws = repository.getById(id)
        workspace = ws
        if (ws != null && ws.isSsh()) {
            manager.ensureSession(ws)
            manager.observeWorkspace(ws.root).collect { tabsState = it }
        }
    }

    val selectedTab = tabsState.tabs.firstOrNull { it.id == tabsState.selectedTabId }
        ?: tabsState.tabs.firstOrNull()

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = selectedTab?.title ?: workspace?.name
                        ?: stringResource(R.string.workspace_terminal_title),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                },
                navigationIcon = { BackButton() },
                actions = {
                    if (selectedTab != null && !selectedTab.finished) {
                        TextButton(onClick = { selectedTab.session.finishIfRunning() }) {
                            Text(stringResource(R.string.workspace_terminal_end))
                        }
                    }
                },
                colors = CustomColors.topBarColors,
            )
        },
        containerColor = Color.Black,
    ) { innerPadding ->
        Surface(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .windowInsetsPadding(WindowInsets.imeAnimationTarget),
            color = Color.Black,
        ) {
            when {
                workspace == null -> TerminalPlaceholder(stringResource(R.string.workspace_terminal_loading))
                workspace?.isSsh() != true -> TerminalPlaceholder(
                    stringResource(R.string.workspace_terminal_not_supported)
                )

                else -> Column(modifier = Modifier.fillMaxSize()) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(MaterialTheme.colorScheme.surface),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        TabRow(
                            selectedTabIndex = tabsState.tabs.indexOfFirst { it.id == selectedTab?.id }
                                .coerceAtLeast(0),
                            modifier = Modifier.weight(1f),
                            containerColor = MaterialTheme.colorScheme.surface,
                            divider = {},
                        ) {
                            tabsState.tabs.forEach { tab ->
                                Tab(
                                    selected = tab.id == selectedTab?.id,
                                    onClick = {
                                        workspace?.let { manager.selectTab(it.root, tab.id) }
                                    },
                                    modifier = Modifier.widthIn(min = 96.dp, max = 180.dp),
                                ) {
                                    Row(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(start = 8.dp),
                                        verticalAlignment = Alignment.CenterVertically,
                                    ) {
                                        Text(
                                            text = tab.title
                                                ?: (stringResource(R.string.workspace_terminal_tab) + " " + tab.number),
                                            modifier = Modifier.weight(1f),
                                            maxLines = 1,
                                            overflow = TextOverflow.Ellipsis,
                                            style = MaterialTheme.typography.labelMedium,
                                        )
                                        IconButton(
                                            onClick = {
                                                workspace?.let { manager.closeTab(it.root, tab.id) }
                                            },
                                            modifier = Modifier.size(32.dp),
                                        ) {
                                            Text(text = "×", fontSize = 16.sp)
                                        }
                                    }
                                }
                            }
                        }
                        IconButton(
                            enabled = workspace != null && !tabsState.isCreating,
                            onClick = { workspace?.let { manager.createTab(it) } },
                        ) {
                            Icon(
                                imageVector = HugeIcons.Add01,
                                contentDescription = stringResource(R.string.workspace_terminal_new_tab),
                                modifier = Modifier.size(22.dp),
                            )
                        }
                    }

                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxWidth(),
                    ) {
                        if (selectedTab != null) {
                            val terminalTextSizePx = with(LocalDensity.current) { 12.sp.roundToPx() }
                            key(selectedTab.id) {
                                AndroidView(
                                    modifier = Modifier.fillMaxSize(),
                                    factory = { viewContext ->
                                        TerminalView(viewContext, null).apply {
                                            isFocusable = true
                                            isFocusableInTouchMode = true
                                            setTextSize(terminalTextSizePx)
                                            setTypeface(Typeface.MONOSPACE)
                                            setTerminalViewClient(viewClient)
                                            attachSession(selectedTab.session)
                                            selectedTab.client.terminalView = this
                                            viewClient.terminalView = this
                                            post { viewClient.focusAndShowKeyboard() }
                                        }
                                    },
                                    update = { terminalView ->
                                        terminalView.isFocusable = true
                                        terminalView.isFocusableInTouchMode = true
                                        terminalView.setTextSize(terminalTextSizePx)
                                        terminalView.setTypeface(Typeface.MONOSPACE)
                                        terminalView.setTerminalViewClient(viewClient)
                                        viewClient.terminalView = terminalView
                                        selectedTab.client.terminalView = terminalView
                                        terminalView.attachSession(selectedTab.session)
                                        terminalView.onScreenUpdated()
                                    },
                                )
                            }
                        } else if (tabsState.isCreating) {
                            TerminalPlaceholder(stringResource(R.string.workspace_terminal_loading))
                        }
                        if (selectedTab?.finished == true) {
                            Text(
                                text = stringResource(R.string.workspace_terminal_exited),
                                modifier = Modifier
                                    .align(Alignment.BottomCenter)
                                    .padding(12.dp),
                                style = MaterialTheme.typography.bodySmall,
                                color = Color.White.copy(alpha = 0.7f),
                            )
                        }
                    }

                    TerminalExtraKeysBar(
                        controlDown = controlDown,
                        altDown = altDown,
                        onControlToggle = { controlDown = !controlDown },
                        onAltToggle = { altDown = !altDown },
                        onSendText = { text ->
                            val current = selectedTab ?: return@TerminalExtraKeysBar
                            val bytes = text.toByteArray()
                            current.session.write(bytes, 0, bytes.size)
                        },
                    )
                }
            }
        }
    }
}

@Composable
private fun TerminalPlaceholder(message: String) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = message,
            style = MaterialTheme.typography.bodyLarge,
            color = Color.White.copy(alpha = 0.7f),
        )
    }
}

@Composable
private fun TerminalExtraKeysBar(
    controlDown: Boolean,
    altDown: Boolean,
    onControlToggle: () -> Unit,
    onAltToggle: () -> Unit,
    onSendText: (String) -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.surface)
            .horizontalScroll(rememberScrollState())
            .padding(horizontal = 8.dp, vertical = 6.dp),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        TerminalExtraKey("ESC") { onSendText("\u001B") }
        TerminalExtraKey("TAB") { onSendText("\t") }
        TerminalExtraKey("CTRL", selected = controlDown, onClick = onControlToggle)
        TerminalExtraKey("ALT", selected = altDown, onClick = onAltToggle)
        TerminalExtraKey("-") { onSendText("-") }
        TerminalExtraKey("/") { onSendText("/") }
        TerminalExtraKey("|") { onSendText("|") }
        TerminalExtraKey("←") { onSendText("\u001B[D") }
        TerminalExtraKey("↓") { onSendText("\u001B[B") }
        TerminalExtraKey("↑") { onSendText("\u001B[A") }
        TerminalExtraKey("→") { onSendText("\u001B[C") }
        TerminalExtraKey("HOME") { onSendText("\u001B[H") }
        TerminalExtraKey("END") { onSendText("\u001B[F") }
    }
}

@Composable
private fun TerminalExtraKey(
    label: String,
    selected: Boolean = false,
    onClick: () -> Unit,
) {
    Text(
        text = label,
        modifier = Modifier
            .background(
                color = if (selected) {
                    MaterialTheme.colorScheme.primary
                } else {
                    MaterialTheme.colorScheme.onSurface.copy(alpha = 0.12f)
                },
                shape = RoundedCornerShape(6.dp),
            )
            .clickable(onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 8.dp),
        style = MaterialTheme.typography.labelMedium,
        color = if (selected) {
            MaterialTheme.colorScheme.onPrimary
        } else {
            MaterialTheme.colorScheme.onSurface.copy(alpha = 0.9f)
        },
    )
}
'''

STRINGS_EN = r'''  <string name="workspace_terminal_tab">Tab</string>
  <string name="workspace_terminal_new_tab">New tab</string>
'''
STRINGS_ZH = r'''  <string name="workspace_terminal_tab">标签</string>
  <string name="workspace_terminal_new_tab">新建标签</string>
'''

diag = []
ok = True

# 1) 新 Manager
mgr_path = "app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/WorkspaceTerminalSessionManager.kt"
if os.path.exists(mgr_path):
    diag.append("manager:exists")
else:
    write(mgr_path, MANAGER)
    diag.append("manager:wrote")

# 2) 整文件重写 Page（355c → 多标签）
page_path = "app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/WorkspaceTerminalPage.kt"
if "WorkspaceTerminalSessionManager" in read(page_path):
    diag.append("page:already-multitab")
else:
    write(page_path, PAGE)
    diag.append("page:rewritten")

# 3) AppModule 注册
app_module = "app/src/main/java/me/rerere/rikkahub/di/AppModule.kt"
text = read(app_module)
ANCHOR = "    single {\n        AppScope()\n    }\n"
REG = (
    "    single {\n"
    "        AppScope()\n"
    "    }\n"
    "\n"
    "    // rhTerminalManager355p: 终端会话按工作区存活, 离开终端页不结束会话\n"
    "    single {\n"
    "        me.rerere.rikkahub.ui.pages.extensions.workspace.WorkspaceTerminalSessionManager(\n"
    "            context = get(),\n"
    "            appScope = get(),\n"
    "            workspaceRepository = get(),\n"
    "        )\n"
    "    }\n"
)
if "WorkspaceTerminalSessionManager(" in text:
    diag.append("di:already")
elif text.count(ANCHOR) == 1:
    text = text.replace(ANCHOR, REG, 1)
    write(app_module, text)
    diag.append("di:ok")
else:
    diag.append("di:ANCHOR-MISMATCH(" + str(text.count(ANCHOR)) + ")")
    ok = False

# 4) strings
for path, block, label in (
    ("app/src/main/res/values/strings.xml", STRINGS_EN, "strings-en"),
    ("app/src/main/res/values-zh/strings.xml", STRINGS_ZH, "strings-zh"),
):
    t = read(path)
    if 'name="workspace_terminal_tab"' in t:
        diag.append(label + ":already")
        continue
    anchor = "</resources>"
    if t.count(anchor) != 1:
        diag.append(label + ":ANCHOR-MISMATCH")
        ok = False
        continue
    write(path, t.replace(anchor, block + anchor, 1))
    diag.append(label + ":ok")

# 5) 自检
def strip_literals(src):
    res = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c == '/' and i + 1 < n and src[i + 1] == '/':
            while i < n and src[i] != '\n':
                i += 1
            continue
        if c == '/' and i + 1 < n and src[i + 1] == '*':
            i += 2
            while i + 1 < n and not (src[i] == '*' and src[i + 1] == '/'):
                i += 1
            i += 2
            continue
        if c == '"':
            if src.startswith('"""', i):
                i += 3
                while i + 2 < n and not src.startswith('"""', i):
                    i += 1
                i += 3
                continue
            i += 1
            while i < n:
                if src[i] == '\\':
                    i += 2
                    continue
                if src[i] == '"':
                    i += 1
                    break
                i += 1
            continue
        if c == "'":
            i += 1
            while i < n:
                if src[i] == '\\':
                    i += 2
                    continue
                if src[i] == "'":
                    i += 1
                    break
                i += 1
            continue
        res.append(c)
        i += 1
    return "".join(res)


for p, label in ((mgr_path, "manager"), (page_path, "page"), (app_module, "appmodule")):
    t = read(p)
    clean = strip_literals(t)
    for pname, left, right in (("braces", "{", "}"), ("parens", "(", ")")):
        d = clean.count(left) - clean.count(right)
        if d != 0:
            diag.append(label + ":" + pname + "-diff=" + str(d))
            ok = False

# 关键符号
mgr_text = read(mgr_path)
for needle in (
    "class WorkspaceTerminalSessionManager internal constructor(",
    "internal fun observeWorkspace(root: String): Flow<WorkspaceTerminalTabsState>",
    "internal fun ensureSession(workspace: WorkspaceEntity)",
    "internal fun createTab(workspace: WorkspaceEntity)",
    "internal fun closeTab(root: String, tabId: Long)",
    "internal data class WorkspaceTerminalTabsState(",
):
    if needle not in mgr_text:
        diag.append("MGR-MISS:" + needle[:44])
        ok = False

page_text = read(page_path)
for needle in (
    "val manager: WorkspaceTerminalSessionManager = koinInject()",
    "manager.ensureSession(ws)",
    "manager.observeWorkspace(ws.root).collect { tabsState = it }",
    "manager.selectTab(it.root, tab.id)",
    "manager.closeTab(it.root, tab.id)",
    "manager.createTab(it)",
    "key(selectedTab.id)",
):
    if needle not in page_text:
        diag.append("PAGE-MISS:" + needle[:44])
        ok = False

final_module = read(app_module)
if "WorkspaceTerminalSessionManager(" not in final_module:
    diag.append("DI-MISS")
    ok = False

diag.append("RESULT:" + ("OK" if ok else "FAIL"))
with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
    f.write("\n".join(diag) + "\n")
print(" | ".join(diag))
if not ok:
    print("::error title=batch355p::" + " | ".join(diag))
