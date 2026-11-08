"""batch372 v2 — 「文件与工具 → 权限管理」

v1（48408d3）已把面板落地，但 MCP 区复用了 McpPickerListItem（二级弹层多选），
用户要的是「开关」，所以 v2 把 MCP 改成内联 Switch 列表（一屏直读直改）。

其余同 v1：
  本地工具（已启用可关 + 显示全部 50 项）/ 记忆（长期·全局·短期，互斥）/ 工作区（就地选择）/ 其他（搜索·最近对话·时间提醒）
  底部保留「快捷消息 · 提示词注入 · 技能」入口，避免原功能变成死入口。

同时把 RhPermSwitchRow 的 supportingContent 改成固定 lambda + 内部条件渲染，
避免 `if (x != null) { { Text() } } else null` 这种 lambda 推断在 Compose 编译器下翻车。
"""

import os

ROOT = os.getcwd()
PICKER = os.path.join(
    ROOT,
    "app/src/main/java/me/rerere/rikkahub/ui/components/ai/FilesPicker.kt",
)
NEWFILE = os.path.join(
    ROOT,
    "app/src/main/java/me/rerere/rikkahub/ui/components/ai/RhPermissionCenter.kt",
)
DIAG = os.path.join(ROOT, "ci_diag_batch372_permission_center.txt")

log = []


def note(m):
    print(m)
    log.append(str(m))


def bal(t):
    return (t.count('{') - t.count('}'), t.count('(') - t.count(')'))


NEW_SRC = r'''package me.rerere.rikkahub.ui.components.ai

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.SheetValue
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import me.rerere.hugeicons.HugeIcons
import me.rerere.hugeicons.stroke.Codesandbox
import me.rerere.hugeicons.stroke.Folder01
import me.rerere.rikkahub.data.ai.mcp.McpManager
import me.rerere.rikkahub.data.ai.tools.LocalToolOption
import me.rerere.rikkahub.data.datastore.Settings
import me.rerere.rikkahub.data.db.entity.WorkspaceEntity
import me.rerere.rikkahub.data.model.Assistant
import kotlin.uuid.Uuid

/** rhPermCenter372: 全部本地工具（sealed class 没有 entries，只能显式列举）。 */
private val RH_ALL_TOOLS: List<LocalToolOption> = listOf(
    LocalToolOption.Files,
    LocalToolOption.ChatUi,
    LocalToolOption.AppControl,
    LocalToolOption.PhoneControl,
    LocalToolOption.Notification,
    LocalToolOption.Toast,
    LocalToolOption.TimeInfo,
    LocalToolOption.AppVersion,
    LocalToolOption.SubAgents,
    LocalToolOption.ImageGeneration,
    LocalToolOption.CustomTools,
    LocalToolOption.Clipboard,
    LocalToolOption.Tts,
    LocalToolOption.AskUser,
    LocalToolOption.Battery,
    LocalToolOption.AudioInfo,
    LocalToolOption.TelephonyInfo,
    LocalToolOption.WifiInfo,
    LocalToolOption.Sensors,
    LocalToolOption.StorageInfo,
    LocalToolOption.Share,
    LocalToolOption.Torch,
    LocalToolOption.Vibrate,
    LocalToolOption.Brightness,
    LocalToolOption.Volume,
    LocalToolOption.MediaPlayer,
    LocalToolOption.MediaScanner,
    LocalToolOption.Download,
    LocalToolOption.Location,
    LocalToolOption.Contacts,
    LocalToolOption.CallLog,
    LocalToolOption.SmsInbox,
    LocalToolOption.CameraPhoto,
    LocalToolOption.MicRecorder,
    LocalToolOption.SpeechToText,
    LocalToolOption.Fingerprint,
    LocalToolOption.McpControl,
    LocalToolOption.CostGuards,
    LocalToolOption.SkillImport,
    LocalToolOption.JsSkills,
    LocalToolOption.SystemIntents,
    LocalToolOption.Browser,
    LocalToolOption.OrangeChat,
    LocalToolOption.SmsSend,
    LocalToolOption.Wallpaper,
    LocalToolOption.Keystore,
    LocalToolOption.Nfc,
    LocalToolOption.ExternalStorage,
    LocalToolOption.Archive,
    LocalToolOption.JavascriptEngine,
)

/** rhPermCenter372: 工具中文名（与「本地工具」设置页保持同义）。 */
private fun rhLocalToolTitle(option: LocalToolOption): String = when (option) {
    LocalToolOption.Files -> "文件读写"
    LocalToolOption.ChatUi -> "聊天界面皮肤"
    LocalToolOption.AppControl -> "应用控制"
    LocalToolOption.PhoneControl -> "手机操控"
    LocalToolOption.Notification -> "发送通知"
    LocalToolOption.Toast -> "Toast 提示"
    LocalToolOption.TimeInfo -> "时间信息"
    LocalToolOption.AppVersion -> "版本信息"
    LocalToolOption.SubAgents -> "子 Agent"
    LocalToolOption.ImageGeneration -> "图片生成"
    LocalToolOption.CustomTools -> "AI 自定义工具"
    LocalToolOption.Clipboard -> "剪贴板"
    LocalToolOption.Tts -> "语音朗读"
    LocalToolOption.AskUser -> "向你提问"
    LocalToolOption.Battery -> "电池信息"
    LocalToolOption.AudioInfo -> "音频信息"
    LocalToolOption.TelephonyInfo -> "运营商信息"
    LocalToolOption.WifiInfo -> "Wi-Fi 信息"
    LocalToolOption.Sensors -> "传感器"
    LocalToolOption.StorageInfo -> "存储信息"
    LocalToolOption.Share -> "分享"
    LocalToolOption.Torch -> "手电筒"
    LocalToolOption.Vibrate -> "振动"
    LocalToolOption.Brightness -> "屏幕亮度"
    LocalToolOption.Volume -> "音量"
    LocalToolOption.MediaPlayer -> "媒体播放"
    LocalToolOption.MediaScanner -> "媒体扫描"
    LocalToolOption.Download -> "下载"
    LocalToolOption.Location -> "定位"
    LocalToolOption.Contacts -> "联系人"
    LocalToolOption.CallLog -> "通话记录"
    LocalToolOption.SmsInbox -> "短信收件箱"
    LocalToolOption.CameraPhoto -> "拍照"
    LocalToolOption.MicRecorder -> "录音"
    LocalToolOption.SpeechToText -> "语音转文字"
    LocalToolOption.Fingerprint -> "指纹"
    LocalToolOption.McpControl -> "MCP 控制"
    LocalToolOption.CostGuards -> "Token 预算"
    LocalToolOption.SkillImport -> "技能安装"
    LocalToolOption.JsSkills -> "JS 技能"
    LocalToolOption.SystemIntents -> "系统意图"
    LocalToolOption.Browser -> "浏览器"
    LocalToolOption.OrangeChat -> "OrangeChat"
    LocalToolOption.SmsSend -> "发送短信"
    LocalToolOption.Wallpaper -> "壁纸"
    LocalToolOption.Keystore -> "密钥库"
    LocalToolOption.Nfc -> "NFC"
    LocalToolOption.ExternalStorage -> "外部存储"
    LocalToolOption.Archive -> "压缩包"
    LocalToolOption.JavascriptEngine -> "JavaScript 引擎"
    else -> option.toString()
}

@Composable
internal fun RhPermissionCenterSheet(
    assistant: Assistant,
    settings: Settings,
    workspaces: List<WorkspaceEntity>,
    mcpManager: McpManager,
    onUpdateAssistant: (Assistant) -> Unit,
    onOpenExtensions: () -> Unit,
    onDismiss: () -> Unit,
) {
    val sheetState = rememberBottomSheetState(
        initialValue = SheetValue.Hidden,
        enabledValues = setOf(SheetValue.Hidden, SheetValue.Expanded),
    )
    var showAllTools by remember { mutableStateOf(false) }
    var showWorkspaceList by remember { mutableStateOf(false) }
    val boundWorkspace = remember(workspaces, assistant.workspaceId) {
        workspaces.find { it.id == assistant.workspaceId?.toString() }
    }

    ModalBottomSheet(onDismissRequest = onDismiss, sheetState = sheetState) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .fillMaxHeight(0.88f)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                text = "权限管理",
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                text = "只显示当前助手允许的能力，开关即时生效",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(4.dp))

            RhPermSection("本地工具", assistant.localTools.size.toString() + " 项已开启")
            if (assistant.localTools.isEmpty()) {
                RhPermHint("未开启任何本地工具")
            } else {
                assistant.localTools.forEach { option ->
                    RhPermSwitchRow(
                        title = rhLocalToolTitle(option),
                        subtitle = null,
                        checked = true,
                        onCheckedChange = { enabled ->
                            if (!enabled) {
                                onUpdateAssistant(
                                    assistant.copy(localTools = assistant.localTools - option)
                                )
                            }
                        },
                    )
                }
            }
            TextButton(onClick = { showAllTools = !showAllTools }) {
                Text(
                    text = if (showAllTools) {
                        "收起全部工具"
                    } else {
                        "显示全部工具（" + RH_ALL_TOOLS.size.toString() + "）"
                    }
                )
            }
            if (showAllTools) {
                RH_ALL_TOOLS.forEach { option ->
                    val checked = assistant.localTools.contains(option)
                    RhPermSwitchRow(
                        title = rhLocalToolTitle(option),
                        subtitle = null,
                        checked = checked,
                        onCheckedChange = { enabled ->
                            val next = if (enabled) {
                                assistant.localTools + option
                            } else {
                                assistant.localTools - option
                            }
                            onUpdateAssistant(assistant.copy(localTools = next))
                        },
                    )
                }
            }

            HorizontalDivider()

            RhPermSection("MCP 服务器", assistant.mcpServers.size.toString() + " 个已启用")
            if (settings.mcpServers.isEmpty()) {
                RhPermHint("未添加 MCP 服务器")
            } else {
                settings.mcpServers.forEach { server ->
                    val serverName = server.commonOptions.name
                    RhPermSwitchRow(
                        title = if (serverName.isBlank()) "MCP 服务器" else serverName,
                        subtitle = if (server.commonOptions.enable) null else "已在设置中禁用",
                        checked = assistant.mcpServers.contains(server.id),
                        onCheckedChange = { enabled ->
                            val next = if (enabled) {
                                assistant.mcpServers + server.id
                            } else {
                                assistant.mcpServers - server.id
                            }
                            onUpdateAssistant(assistant.copy(mcpServers = next))
                        },
                    )
                }
            }

            HorizontalDivider()

            RhPermSection("记忆", null)
            RhPermSwitchRow(
                title = "长期记忆",
                subtitle = "跨会话记住关于你的事",
                checked = assistant.enableMemory,
                onCheckedChange = { enabled ->
                    onUpdateAssistant(
                        assistant.copy(
                            enableMemory = enabled,
                            enableShortMemory = if (enabled) false else assistant.enableShortMemory,
                        )
                    )
                },
            )
            if (assistant.enableMemory) {
                RhPermSwitchRow(
                    title = "使用全局共享记忆",
                    subtitle = "关闭时只用本助手自己的记忆",
                    checked = assistant.useGlobalMemory,
                    onCheckedChange = { enabled ->
                        onUpdateAssistant(assistant.copy(useGlobalMemory = enabled))
                    },
                )
            }
            RhPermSwitchRow(
                title = "短期记忆",
                subtitle = "只在本对话内生效，与长期记忆互斥",
                checked = assistant.enableShortMemory,
                onCheckedChange = { enabled ->
                    onUpdateAssistant(
                        assistant.copy(
                            enableShortMemory = enabled,
                            enableMemory = if (enabled) false else assistant.enableMemory,
                        )
                    )
                },
            )

            HorizontalDivider()

            RhPermSection("工作区", if (boundWorkspace != null) "已绑定" else "未绑定")
            ListItem(
                leadingContent = {
                    Icon(
                        imageVector = HugeIcons.Codesandbox,
                        contentDescription = null,
                    )
                },
                headlineContent = { Text("绑定工作区") },
                supportingContent = {
                    Text(
                        text = boundWorkspace?.name ?: "未绑定",
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                },
                trailingContent = {
                    Text(
                        text = if (showWorkspaceList) "收起" else "选择",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary,
                    )
                },
                colors = ListItemDefaults.colors(
                    containerColor = MaterialTheme.colorScheme.surfaceContainer
                ),
                modifier = Modifier
                    .clip(MaterialTheme.shapes.large)
                    .clickable { showWorkspaceList = !showWorkspaceList },
            )
            if (showWorkspaceList) {
                RhPermChoiceRow(
                    title = "不绑定",
                    selected = assistant.workspaceId == null,
                    onClick = {
                        onUpdateAssistant(assistant.copy(workspaceId = null))
                        showWorkspaceList = false
                    },
                )
                workspaces.forEach { workspace ->
                    RhPermChoiceRow(
                        title = workspace.name,
                        selected = assistant.workspaceId?.toString() == workspace.id,
                        onClick = {
                            val parsed = runCatching { Uuid.parse(workspace.id) }.getOrNull()
                            if (parsed != null) {
                                onUpdateAssistant(assistant.copy(workspaceId = parsed))
                            }
                            showWorkspaceList = false
                        },
                    )
                }
            }

            HorizontalDivider()

            RhPermSection("其他能力", null)
            RhPermSwitchRow(
                title = "联网搜索",
                subtitle = "开启后本轮使用搜索工具",
                checked = assistant.enableWebSearch,
                onCheckedChange = { enabled ->
                    onUpdateAssistant(assistant.copy(enableWebSearch = enabled))
                },
            )
            RhPermSwitchRow(
                title = "引用最近对话",
                subtitle = "允许把最近几段对话作为参考",
                checked = assistant.enableRecentChatsReference,
                onCheckedChange = { enabled ->
                    onUpdateAssistant(assistant.copy(enableRecentChatsReference = enabled))
                },
            )
            RhPermSwitchRow(
                title = "时间提醒注入",
                subtitle = "按间隔在上下文里补一句当前时间",
                checked = assistant.enableTimeReminder,
                onCheckedChange = { enabled ->
                    onUpdateAssistant(assistant.copy(enableTimeReminder = enabled))
                },
            )

            HorizontalDivider()
            TextButton(onClick = onOpenExtensions, modifier = Modifier.fillMaxWidth()) {
                Text("快捷消息 · 提示词注入 · 技能")
            }
            TextButton(onClick = onDismiss, modifier = Modifier.fillMaxWidth()) {
                Text("关闭")
            }
            Spacer(Modifier.height(16.dp))
        }
    }
}

@Composable
private fun RhPermSection(title: String, badge: String?) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.titleSmall,
            color = MaterialTheme.colorScheme.primary,
        )
        if (badge != null) {
            Spacer(Modifier.width(8.dp))
            Text(
                text = badge,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun RhPermHint(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp),
    )
}

@Composable
private fun RhPermSubtitle(text: String?) {
    if (text == null) {
        return
    }
    Text(
        text = text,
        maxLines = 2,
        overflow = TextOverflow.Ellipsis,
    )
}

@Composable
private fun RhPermSwitchRow(
    title: String,
    subtitle: String?,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
) {
    ListItem(
        headlineContent = { Text(title) },
        supportingContent = { RhPermSubtitle(subtitle) },
        trailingContent = {
            Switch(checked = checked, onCheckedChange = onCheckedChange)
        },
        colors = ListItemDefaults.colors(
            containerColor = MaterialTheme.colorScheme.surfaceContainer
        ),
        modifier = Modifier
            .clip(MaterialTheme.shapes.large)
            .clickable { onCheckedChange(!checked) },
    )
}

@Composable
private fun RhPermChoiceRow(title: String, selected: Boolean, onClick: () -> Unit) {
    ListItem(
        leadingContent = {
            Icon(
                imageVector = HugeIcons.Folder01,
                contentDescription = null,
            )
        },
        headlineContent = {
            Text(text = title, maxLines = 1, overflow = TextOverflow.Ellipsis)
        },
        trailingContent = {
            if (selected) {
                Text(text = "已选", color = MaterialTheme.colorScheme.primary)
            }
        },
        colors = ListItemDefaults.colors(
            containerColor = MaterialTheme.colorScheme.surfaceContainerLow
        ),
        modifier = Modifier
            .clip(MaterialTheme.shapes.large)
            .clickable(onClick = onClick),
    )
}
'''

NEW_BLOCK = '''        // rhPermCenter372: 「权限管理」——只列当前助手已允许的能力，并可直接开关。
        var showPermissionCenter by remember { mutableStateOf(false) }
        ListItem(
            leadingContent = {
                Icon(
                    imageVector = HugeIcons.Settings02,
                    contentDescription = null,
                )
            },
            headlineContent = { Text("权限管理") },
            supportingContent = {
                Text(
                    text = "本地工具 " + assistant.localTools.size + " · MCP " + assistant.mcpServers.size +
                        " · 记忆" + (if (assistant.enableMemory || assistant.enableShortMemory) "开" else "关") +
                        " · 工作区" + (if (assistant.workspaceId != null) "已绑定" else "未绑定"),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            },
            trailingContent = {
                Text(
                    text = "›",
                    style = MaterialTheme.typography.titleLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            },
            colors = ListItemDefaults.colors(
                containerColor = MaterialTheme.colorScheme.surfaceContainer
            ),
            modifier = Modifier
                .clip(MaterialTheme.shapes.large)
                .clickable { showPermissionCenter = true },
        )
        if (showPermissionCenter) {
            RhPermissionCenterSheet(
                assistant = assistant,
                settings = settings,
                workspaces = workspaces,
                mcpManager = mcpManager,
                onUpdateAssistant = onUpdateAssistant,
                onOpenExtensions = {
                    showPermissionCenter = false
                    onShowInjectionSheetChange(true)
                },
                onDismiss = { showPermissionCenter = false },
            )
        }

'''

START = "        // Extensions (Quick Messages + Prompt Injections + Skills)"
END = "        // rhHeartRate: live heart-rate broadcast entry"


def main():
    picker = open(PICKER, "r", encoding="utf-8").read()

    if "rhPermCenter372" in picker:
        note("picker already patched, skip")
        if "RhPermissionCenterSheet(" not in picker:
            note("FAIL sheet call missing in patched picker")
            open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
            raise SystemExit(1)
    else:
        before = bal(picker)
        if picker.count(START) != 1:
            note("FAIL start anchor count=" + str(picker.count(START)))
            open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
            raise SystemExit(1)
        if picker.count(END) != 1:
            note("FAIL end anchor count=" + str(picker.count(END)))
            open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
            raise SystemExit(1)
        i = picker.index(START)
        j = picker.index(END)
        if j <= i:
            note("FAIL end before start")
            open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
            raise SystemExit(1)
        note("old block len=" + str(j - i))
        new_picker = picker[:i] + NEW_BLOCK + picker[j:]
        after = bal(new_picker)
        note("picker balance " + str(before) + " -> " + str(after))
        if after != before:
            note("FAIL picker balance drift")
            open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
            raise SystemExit(1)
        if "RhPermissionCenterSheet(" not in new_picker:
            note("FAIL sheet call missing")
            open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
            raise SystemExit(1)
        open(PICKER, "w", encoding="utf-8").write(new_picker)
        note("picker rewritten")

    check = bal(NEW_SRC)
    note("v2 source balance " + str(check) + " len=" + str(len(NEW_SRC)))
    if check != (0, 0):
        note("FAIL v2 source unbalanced")
        open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
        raise SystemExit(1)
    open(NEWFILE, "w", encoding="utf-8").write(NEW_SRC)

    src = open(NEWFILE, "r", encoding="utf-8").read()
    must = [
        "rhPermCenter372",
        "RhPermissionCenterSheet",
        "RH_ALL_TOOLS",
        "assistant.copy(mcpServers = next)",
        "RhPermSubtitle",
        "快捷消息 · 提示词注入 · 技能",
    ]
    for item in must:
        if item not in src:
            note("FAIL missing " + item)
            open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
            raise SystemExit(1)
    if "McpPickerListItem(" in src:
        note("FAIL old mcp picker still used")
        open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
        raise SystemExit(1)

    note("tool refs=" + str(src.count("LocalToolOption.")))
    note("DONE permission center v2 (mcp inline switches)")
    print("::error title=rhPermCenter372::OK 权限管理面板 v2：本地工具/MCP/记忆/工作区/其他能力 全部真开关")
    open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")


main()
