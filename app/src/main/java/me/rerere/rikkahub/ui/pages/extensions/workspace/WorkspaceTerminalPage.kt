package me.rerere.rikkahub.ui.pages.extensions.workspace

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
        if (ws != null) {
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
                else -> Column(modifier = Modifier.fillMaxSize()) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(MaterialTheme.colorScheme.surface),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        if (tabsState.tabs.isEmpty()) {
                            // 建连窗口内 tabs 为空: TabRow(selectedTabIndex=0) 会越界崩溃
                            Box(modifier = Modifier.weight(1f))
                        } else {
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
                        } else if (tabsState.lastError != null) {
                            TerminalPlaceholder(tabsState.lastError ?: "")
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
