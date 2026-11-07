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
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
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
import com.termux.terminal.TerminalSession
import com.termux.view.TerminalView
import me.rerere.rikkahub.R
import me.rerere.rikkahub.data.db.entity.WorkspaceEntity
import me.rerere.rikkahub.data.repository.WorkspaceRepository
import me.rerere.rikkahub.ui.components.nav.BackButton
import me.rerere.rikkahub.ui.theme.CustomColors
import org.koin.compose.koinInject

/** 按工作区存活的终端会话; 离开页面不杀会话, 重进可继续, 空闲由 SSH 连接池 5 分钟回收兜底 */
private val terminalSessions = mutableMapOf<String, TerminalSession>()

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun WorkspaceTerminalPage(id: String) {
    val context = LocalContext.current
    val repository: WorkspaceRepository = koinInject()
    var workspace by remember(id) { mutableStateOf<WorkspaceEntity?>(null) }
    var session by remember(id) { mutableStateOf<TerminalSession?>(null) }
    var title by remember(id) { mutableStateOf<String?>(null) }
    var finished by remember(id) { mutableStateOf(false) }
    var controlDown by remember(id) { mutableStateOf(false) }
    var altDown by remember(id) { mutableStateOf(false) }
    val viewClient = remember(id) { WorkspaceTerminalViewClient(context) }
    viewClient.controlDown = controlDown
    viewClient.altDown = altDown

    LaunchedEffect(id) {
        val ws = repository.getById(id)
        workspace = ws
        if (ws != null && ws.isSsh()) {
            val settings = ws.sshSettings()
            if (settings != null) {
                val address = "${settings.username}@${settings.host}:${settings.port}"
                val existing = terminalSessions[id]
                session = if (existing != null && existing.isRunning) {
                    existing
                } else {
                    terminalSessions.remove(id)
                    val client = WorkspaceTerminalSessionClient(
                        context = context,
                        onTitleUpdated = { title = it },
                        onFinished = { finished = true },
                    )
                    val transport = SshTerminalTransport(address) { columns, rows ->
                        repository.openSshShell(ws, columns, rows)
                    }
                    createWorkspaceTerminalSession(transport, ws.root, client).also {
                        terminalSessions[id] = it
                    }
                }
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = title ?: workspace?.name
                        ?: stringResource(R.string.workspace_terminal_title),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                },
                navigationIcon = { BackButton() },
                actions = {
                    if (session != null && !finished) {
                        TextButton(onClick = { session?.finishIfRunning() }) {
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
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxWidth(),
                    ) {
                        val current = session
                        if (current != null) {
                            val terminalTextSizePx = with(LocalDensity.current) { 12.sp.roundToPx() }
                            AndroidView(
                                modifier = Modifier.fillMaxSize(),
                                factory = { viewContext ->
                                    TerminalView(viewContext, null).apply {
                                        isFocusable = true
                                        isFocusableInTouchMode = true
                                        setTextSize(terminalTextSizePx)
                                        setTypeface(Typeface.MONOSPACE)
                                        setTerminalViewClient(viewClient)
                                        attachSession(current)
                                        viewClient.terminalView = this
                                        post {
                                            viewClient.focusAndShowKeyboard()
                                        }
                                    }
                                },
                                update = { terminalView ->
                                    terminalView.isFocusable = true
                                    terminalView.isFocusableInTouchMode = true
                                    terminalView.setTextSize(terminalTextSizePx)
                                    terminalView.setTypeface(Typeface.MONOSPACE)
                                    terminalView.setTerminalViewClient(viewClient)
                                    viewClient.terminalView = terminalView
                                    terminalView.attachSession(current)
                                    terminalView.onScreenUpdated()
                                },
                            )
                        }
                        if (finished) {
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
                            val current = session ?: return@TerminalExtraKeysBar
                            val bytes = text.toByteArray()
                            current.write(bytes, 0, bytes.size)
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
