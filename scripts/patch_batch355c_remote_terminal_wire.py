#!/usr/bin/env python3
# rhRemote355c: SSH 终端接入 app —— SshTerminalTransport + 终端页 + 路由 + 详情入口
# v2 修正(推送前自查): 补 TextButton import; 加 @OptIn(ExperimentalLayoutApi);
# 扩展键转义序列用 Kotlin 字面 \u001B(raw 字符串原样保留), 上版控制字符被吞。
import os

DIAG = "ci_diag_batch355c_remote.txt"
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


TRANSPORT = r'''package me.rerere.rikkahub.ui.pages.extensions.workspace

import com.termux.terminal.TerminalTransport
import me.rerere.workspace.ssh.SshShell
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.util.concurrent.Executors
import java.util.concurrent.RejectedExecutionException

/**
 * 把远程 [SshShell] 接到终端会话上。
 *
 * 调整尺寸和关闭都要走网络, 而终端在主线程调用它们, 所以统一交给一个后台线程按顺序执行。
 */
internal class SshTerminalTransport(
    /** 连接目标, 如 user@host:22, 连接期间显示在终端里 */
    private val address: String,
    private val openShell: (columns: Int, rows: Int) -> SshShell,
) : TerminalTransport {
    private val control = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "ssh-terminal-control").apply { isDaemon = true }
    }

    @Volatile
    private var shell: SshShell? = null

    @Volatile
    private var killed = false

    @Volatile
    private var remoteExitStatus: Int? = null

    @Volatile
    private var connectionLost = false

    override fun start(columns: Int, rows: Int) {
        val opened = openShell(columns, rows)
        shell = opened
        // 连接期间页面已被关掉: kill() 那时还拿不到 shell, 由这里收尾
        if (killed) {
            opened.close()
            throw IOException("Terminal closed")
        }
    }

    override fun getInputStream(): InputStream = requireShell().inputStream

    override fun getOutputStream(): OutputStream = requireShell().outputStream

    override fun setWindowSize(columns: Int, rows: Int) {
        val shell = shell ?: return
        runControl { shell.resize(columns, rows) }
    }

    override fun waitFor(): Int {
        val shell = requireShell()
        val status = shell.waitFor()
        remoteExitStatus = status
        connectionLost = status == null && shell.connectionLost
        return status ?: -1
    }

    override fun kill() {
        killed = true
        val shell = shell ?: return
        runControl { shell.close() }
    }

    override fun close() {
        val shell = shell
        runControl { shell?.close() }
        control.shutdown()
    }

    override fun describeStart(): String = "Connecting to $address..."

    override fun describeExit(exitStatus: Int): String = when {
        remoteExitStatus != null -> super.describeExit(exitStatus)
        connectionLost -> "Connection lost"
        else -> "Session closed"
    }

    private fun requireShell(): SshShell = shell ?: error("SSH shell is not started")

    private fun runControl(block: () -> Unit) {
        try {
            control.execute { runCatching(block) }
        } catch (_: RejectedExecutionException) {
            // 已经 close, shell 也已关闭
        }
    }
}
'''

SESSION = r'''package me.rerere.rikkahub.ui.pages.extensions.workspace

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.util.Log
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.inputmethod.InputMethodManager
import androidx.core.net.toUri
import com.termux.terminal.TerminalEmulator
import com.termux.terminal.TerminalSession
import com.termux.terminal.TerminalSessionClient
import com.termux.terminal.TerminalTransport
import com.termux.view.TerminalView
import com.termux.view.TerminalViewClient

internal fun createWorkspaceTerminalSession(
    transport: TerminalTransport,
    root: String,
    client: TerminalSessionClient,
): TerminalSession =
    TerminalSession(transport, 2_000, client).apply {
        mSessionName = root
    }

internal class WorkspaceTerminalSessionClient(
    private val context: Context,
    private val onTitleUpdated: (String?) -> Unit,
    private val onFinished: () -> Unit,
) : TerminalSessionClient {
    var terminalView: TerminalView? = null

    override fun onTextChanged(changedSession: TerminalSession) {
        terminalView?.onScreenUpdated()
    }

    override fun onTitleChanged(changedSession: TerminalSession) {
        onTitleUpdated(changedSession.title)
    }

    override fun onSessionFinished(finishedSession: TerminalSession) {
        terminalView?.onScreenUpdated()
        onFinished()
    }

    override fun onCopyTextToClipboard(session: TerminalSession, text: String) {
        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText("terminal", text))
    }

    override fun onPasteTextFromClipboard(session: TerminalSession) {
        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        val text = clipboard.primaryClip
            ?.takeIf { it.itemCount > 0 }
            ?.getItemAt(0)
            ?.coerceToText(context)
            ?.toString()
            ?: return
        val bytes = text.toByteArray()
        session.write(bytes, 0, bytes.size)
    }

    override fun onBell(session: TerminalSession) = Unit

    override fun onColorsChanged(session: TerminalSession) {
        terminalView?.invalidate()
    }

    override fun onTerminalCursorStateChange(state: Boolean) {
        terminalView?.invalidate()
    }

    override fun getTerminalCursorStyle(): Int =
        TerminalEmulator.DEFAULT_TERMINAL_CURSOR_STYLE

    override fun logError(tag: String, message: String) {
        Log.e(tag, message)
    }

    override fun logWarn(tag: String, message: String) {
        Log.w(tag, message)
    }

    override fun logInfo(tag: String, message: String) {
        Log.i(tag, message)
    }

    override fun logDebug(tag: String, message: String) {
        Log.d(tag, message)
    }

    override fun logVerbose(tag: String, message: String) {
        Log.v(tag, message)
    }

    override fun logStackTraceWithMessage(tag: String, message: String, e: Exception) {
        Log.e(tag, message, e)
    }

    override fun logStackTrace(tag: String, e: Exception) {
        Log.e(tag, "Terminal error", e)
    }
}

internal class WorkspaceTerminalViewClient(
    private val context: Context,
) : TerminalViewClient {
    var terminalView: TerminalView? = null
    var controlDown: Boolean = false
    var altDown: Boolean = false

    override fun onScale(scale: Float): Float = scale.coerceIn(0.8f, 1.25f)

    override fun onSingleTapUp(e: MotionEvent) {
        if (openUrlAtTap(e)) return
        focusAndShowKeyboard()
    }

    /**
     * 检测点击位置是否落在一个 URL 上, 是则用浏览器打开并返回 true.
     * TerminalView 0.118.0 没有内置链接点击, 这里基于 getColumnAndRow() + 屏幕缓冲文本自行实现,
     * 并通过 getLineWrap() 还原被软换行拆开的长 URL.
     */
    private fun openUrlAtTap(e: MotionEvent): Boolean {
        val view = terminalView ?: return false
        if (view.isSelectingText) return false
        val emulator = view.mEmulator ?: return false
        val screen = emulator.getScreen()
        val columns = emulator.mColumns
        val columnAndRow = view.getColumnAndRow(e, true)
        val column = columnAndRow[0]
        val row = columnAndRow[1]
        val rows = emulator.mRows
        val minAccessibleRow = -screen.activeTranscriptRows
        val maxAccessibleRow = rows - 1
        if (column < 0 || column >= columns) return false
        if (row < minAccessibleRow || row > maxAccessibleRow) return false

        val minRow = (row - URL_MAX_WRAP_ROWS).coerceAtLeast(minAccessibleRow)
        val maxRow = (row + URL_MAX_WRAP_ROWS).coerceAtMost(maxAccessibleRow)
        var startRow = row
        while (startRow > minRow && screen.getLineWrap(startRow - 1)) startRow--
        var endRow = row
        while (endRow < maxRow && screen.getLineWrap(endRow)) endRow++

        val line = StringBuilder()
        var tapIndex = -1
        for (r in startRow..endRow) {
            if (r == row) {
                tapIndex = line.length + (screen.getSelectedText(0, r, column, r).length - 1).coerceAtLeast(0)
            }
            line.append(screen.getSelectedText(0, r, columns - 1, r))
        }
        if (tapIndex < 0) return false

        val match = URL_REGEX.findAll(line).firstOrNull { tapIndex in it.range } ?: return false
        val url = match.value.trimEnd(*URL_TRAILING_TRIM)
        return runCatching {
            val intent = Intent(Intent.ACTION_VIEW, url.toUri())
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(intent)
            true
        }.getOrElse {
            Log.w("WorkspaceTerminal", "Failed to open url: $url", it)
            false
        }
    }

    fun focusAndShowKeyboard() {
        val view = terminalView ?: return
        val inputMethodManager = context.getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager
        view.post {
            view.requestFocus()
            inputMethodManager.showSoftInput(view, InputMethodManager.SHOW_IMPLICIT)
        }
    }

    override fun shouldBackButtonBeMappedToEscape(): Boolean = false

    override fun shouldEnforceCharBasedInput(): Boolean = true

    override fun shouldUseCtrlSpaceWorkaround(): Boolean = false

    override fun isTerminalViewSelected(): Boolean = true

    override fun copyModeChanged(copyMode: Boolean) = Unit

    override fun onKeyDown(keyCode: Int, e: KeyEvent, session: TerminalSession): Boolean = false

    override fun onKeyUp(keyCode: Int, e: KeyEvent): Boolean = false

    override fun onLongPress(event: MotionEvent): Boolean = false

    override fun readControlKey(): Boolean = controlDown

    override fun readAltKey(): Boolean = altDown

    override fun readShiftKey(): Boolean = false

    override fun readFnKey(): Boolean = false

    override fun onCodePoint(codePoint: Int, ctrlDown: Boolean, session: TerminalSession): Boolean = false

    override fun onEmulatorSet() = Unit

    override fun logError(tag: String, message: String) {
        Log.e(tag, message)
    }

    override fun logWarn(tag: String, message: String) {
        Log.w(tag, message)
    }

    override fun logInfo(tag: String, message: String) {
        Log.i(tag, message)
    }

    override fun logDebug(tag: String, message: String) {
        Log.d(tag, message)
    }

    override fun logVerbose(tag: String, message: String) {
        Log.v(tag, message)
    }

    override fun logStackTraceWithMessage(tag: String, message: String, e: Exception) {
        Log.e(tag, message, e)
    }

    override fun logStackTrace(tag: String, e: Exception) {
        Log.e(tag, "Terminal view error", e)
    }
}

// 一个 URL 最多还原跨越的软换行行数(向上/向下各算), 足够覆盖任意真实 URL
private const val URL_MAX_WRAP_ROWS = 50

private val URL_REGEX =
    Regex("""(https?|ftp)://[\w\-._~:/?#\[\]@!$&'()*+,;=%]+""", RegexOption.IGNORE_CASE)

// 终端里 URL 后面常跟标点(行尾句号、被括号包裹等), 打开前去掉这些结尾字符
private val URL_TRAILING_TRIM = charArrayOf('.', ',', ';', ':', '!', '?', ')', ']', '}', '\'', '"')
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
'''

STRINGS_EN = r'''  <string name="workspace_terminal_title">Terminal</string>
  <string name="workspace_terminal_end">End session</string>
  <string name="workspace_terminal_exited">Session ended</string>
  <string name="workspace_terminal_loading">Loading…</string>
  <string name="workspace_terminal_not_supported">Terminal is not available for this workspace</string>
'''
STRINGS_ZH = r'''  <string name="workspace_terminal_title">终端</string>
  <string name="workspace_terminal_end">结束会话</string>
  <string name="workspace_terminal_exited">会话已结束</string>
  <string name="workspace_terminal_loading">加载中…</string>
  <string name="workspace_terminal_not_supported">该工作区不支持终端</string>
'''


def patch(path, edits, diag):
    text = read(path)
    for label, needle, repl in edits:
        if repl in text:
            diag.append(label + ":already")
            continue
        if text.count(needle) != 1:
            diag.append(label + ":ANCHOR-MISMATCH(" + str(text.count(needle)) + ")")
            continue
        text = text.replace(needle, repl, 1)
        diag.append(label + ":ok")
    write(path, text)


def main():
    diag = []
    ok = True

    base = "app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/"
    for rel, content, label in (
        ("SshTerminalTransport.kt", TRANSPORT, "transport"),
        ("WorkspaceTerminalSession.kt", SESSION, "session"),
        ("WorkspaceTerminalPage.kt", PAGE, "page"),
    ):
        path = base + rel
        if os.path.exists(path):
            diag.append(label + ":exists")
        else:
            write(path, content)
            diag.append(label + ":wrote")
        if content.count("{") != content.count("}"):
            diag.append(label + ":BRACES")
            ok = False
        if content.count("(") != content.count(")"):
            diag.append(label + ":PARENS")
            ok = False
    # v2 自检: 转义序列必须是六字符字面 \u001B 而不是真实控制字符
    if "\x1b" in PAGE:
        diag.append("page:RAW-CONTROL-CHAR")
        ok = False
    if "\\u001B" not in PAGE:
        diag.append("page:MISSING-ESC-LITERAL")
        ok = False
    if "import androidx.compose.material3.TextButton" not in PAGE:
        diag.append("page:MISSING-TextButton-import")
        ok = False
    if "@OptIn(ExperimentalLayoutApi::class)" not in PAGE:
        diag.append("page:MISSING-OptIn")
        ok = False

    # Workspace.kt: SSH terminal 打开
    patch("workspace/src/main/java/me/rerere/workspace/Workspace.kt", [
        (
            "ssh-terminal",
            "/** 通过 SSH 连接的远程机器 */\n    SSH(\n        WorkspaceCapabilities(\n            rootfs = false,\n            terminal = false,",
            "/** 通过 SSH 连接的远程机器 */\n    SSH(\n        WorkspaceCapabilities(\n            rootfs = false,\n            terminal = true,",
        ),
    ], diag)

    # 依赖: version catalog + app modules
    patch("gradle/libs.versions.toml", [
        (
            "ver",
            'jsch = "2.28.8"',
            'jsch = "2.28.8"\ntermux = "0.118.0"',
        ),
        (
            "lib",
            'jsch = { module = "com.github.mwiede:jsch", version.ref = "jsch" }',
            'jsch = { module = "com.github.mwiede:jsch", version.ref = "jsch" }\n'
            'termux-terminal-view = { module = "com.termux.termux-app:terminal-view", version.ref = "termux" }',
        ),
    ], diag)

    patch("app/build.gradle.kts", [
        (
            "app-modules",
            '    implementation(project(":workspace"))',
            '    implementation(project(":workspace"))\n'
            '    implementation(project(":terminal"))\n'
            '    implementation(libs.termux.terminal.view) {\n'
            '        exclude(group = "com.termux.termux-app", module = "terminal-emulator")\n'
            '    }',
        ),
    ], diag)

    # 路由: Screen + entry + import
    patch("app/src/main/java/me/rerere/rikkahub/RouteActivity.kt", [
        (
            "route-import",
            "import me.rerere.rikkahub.ui.pages.extensions.workspace.WorkspaceSshEditorPage\n",
            "import me.rerere.rikkahub.ui.pages.extensions.workspace.WorkspaceSshEditorPage\n"
            "import me.rerere.rikkahub.ui.pages.extensions.workspace.WorkspaceTerminalPage\n",
        ),
        (
            "route-screen",
            "    @Serializable\n    data class WorkspaceSshEditor(val id: String? = null) : Screen\n",
            "    @Serializable\n    data class WorkspaceSshEditor(val id: String? = null) : Screen\n\n"
            "    @Serializable\n    data class WorkspaceTerminal(val id: String) : Screen\n",
        ),
        (
            "route-entry",
            "                            entry<Screen.WorkspaceSshEditor> { key ->\n"
            "                                WorkspaceSshEditorPage(key.id)\n"
            "                            }\n",
            "                            entry<Screen.WorkspaceSshEditor> { key ->\n"
            "                                WorkspaceSshEditorPage(key.id)\n"
            "                            }\n\n"
            "                            entry<Screen.WorkspaceTerminal> { key ->\n"
            "                                WorkspaceTerminalPage(key.id)\n"
            "                            }\n",
        ),
    ], diag)

    # 详情页: 终端按钮(在 SSH 编辑按钮之前)
    patch("app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/WorkspaceDetailPage.kt", [
        (
            "detail-terminal",
            "                    if (state.workspace?.isSsh() == true) {",
            "                    if (state.workspace?.supportsTerminal() == true) {\n"
            "                        IconButton(onClick = { navController.navigate(Screen.WorkspaceTerminal(state.workspace!!.id)) }) {\n"
            "                            Icon(HugeIcons.Settings03, contentDescription = stringResource(R.string.workspace_terminal_title))\n"
            "                        }\n"
            "                    }\n"
            "                    if (state.workspace?.isSsh() == true) {",
        ),
    ], diag)

    # strings
    for path, block, label in (
        ("app/src/main/res/values/strings.xml", STRINGS_EN, "strings-en"),
        ("app/src/main/res/values-zh/strings.xml", STRINGS_ZH, "strings-zh"),
    ):
        text = read(path)
        if 'name="workspace_terminal_title"' in text:
            diag.append(label + ":already")
            continue
        anchor = "</resources>"
        if text.count(anchor) != 1:
            diag.append(label + ":ANCHOR-MISMATCH")
            ok = False
            continue
        text = text.replace(anchor, block + "\n" + anchor, 1)
        write(path, text)
        diag.append(label + ":ok")

    # 落地自检
    wk = read("workspace/src/main/java/me/rerere/workspace/Workspace.kt")
    if wk.count("terminal = false,") != 1:
        diag.append("workspace.kt:terminal-count=" + str(wk.count("terminal = false,")))
        ok = False
    toml = read("gradle/libs.versions.toml")
    if 'termux = "0.118.0"' not in toml or "termux-terminal-view" not in toml:
        diag.append("toml:MISS")
        ok = False
    appg = read("app/build.gradle.kts")
    if 'project(":terminal")' not in appg or "termux.terminal.view" not in appg:
        diag.append("app-gradle:MISS")
        ok = False
    route = read("app/src/main/java/me/rerere/rikkahub/RouteActivity.kt")
    if "WorkspaceTerminal(val id: String)" not in route or "WorkspaceTerminalPage(key.id)" not in route:
        diag.append("route:MISS")
        ok = False
    detail = read("app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/WorkspaceDetailPage.kt")
    if "Screen.WorkspaceTerminal(" not in detail:
        diag.append("detail:MISS")
        ok = False
    for needle in (
        "internal class SshTerminalTransport(",
        "internal class WorkspaceTerminalSessionClient(",
        "internal class WorkspaceTerminalViewClient(",
        "fun WorkspaceTerminalPage(id: String)",
        "repository.openSshShell(ws, columns, rows)",
        "TerminalExtraKeysBar(",
    ):
        if needle not in (TRANSPORT + SESSION + PAGE):
            diag.append("src:MISSING:" + needle[:40])
            ok = False

    diag.append("RESULT:" + ("OK" if ok else "FAIL"))
    with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
        f.write("\n".join(diag) + "\n")
    print(" | ".join(diag))
    if not ok:
        print("::error title=batch355c::" + " | ".join(diag))


main()
