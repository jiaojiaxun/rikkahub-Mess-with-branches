"""batch372 — 「文件与工具 → 权限管理」

用户反馈：聊天框 → 文件与工具 → 里面的入口点开是「快捷消息 / 模式注入 / 世界书 / 技能」，
内容不对。要求改成权限中心，只显示：
  助手本地工具内允许的权限 + MCP + 记忆 + 工作区 等等
并且每项都有类似开关可以直接开关。

做法：
1) 新建 RhPermissionCenter.kt（同包）：分组列表面板
   - 本地工具：先列「已开启」的（Switch 可直接关），再给一个「显示全部工具」展开全量 50 项
   - MCP：复用同包 McpPickerListItem（多选服务器）
   - 记忆：长期 / 全局共享 / 短期（互斥处理）
   - 工作区：绑定 / 解绑（就地选择）
   - 其他：联网搜索 / 最近对话引用 / 时间提醒
   - 底部保留「快捷消息 · 提示词注入 · 技能」入口，避免功能变死
2) FilesPicker.kt：把原来的「扩展」行替换成「权限管理」行，点击打开新面板。

锚点按 CI 真形态（snapshot）写：起止标记切片，不做整块精确匹配。
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
import me.rerere.hugeicons.stroke.Settings02
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
                McpPickerListItem(
                    assistant = assistant,
                    servers = settings.mcpServers,
                    mcpManager = mcpManager,
                    onUpdateAssistant = onUpdateAssistant,
                )
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
private fun RhPermSwitchRow(
    title: String,
    subtitle: String?,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
) {
    ListItem(
        headlineContent = { Text(title) },
        supportingContent = if (subtitle != null) {
            { Text(subtitle, maxLines = 2, overflow = TextOverflow.Ellipsis) }
        } else {
            null
        },
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
    before = bal(picker)

    if "rhPermCenter372" in picker:
        note("picker already patched, skip")
    else:
        if picker.count(START) != 1:
            note("FAIL start anchor count=" + str(picker.count(START)))
            raise SystemExit(1)
        if picker.count(END) != 1:
            note("FAIL end anchor count=" + str(picker.count(END)))
            raise SystemExit(1)
        i = picker.index(START)
        j = picker.index(END)
        if j <= i:
            note("FAIL end before start")
            raise SystemExit(1)
        old_block = picker[i:j]
        note("old block len=" + str(len(old_block)))

        new_picker = picker[:i] + NEW_BLOCK + picker[j:]
        after = bal(new_picker)
        note("picker balance " + str(before) + " -> " + str(after))
        if after != before:
            note("FAIL picker balance drift")
            raise SystemExit(1)
        if "RhPermissionCenterSheet(" not in new_picker:
            note("FAIL sheet call missing")
            raise SystemExit(1)

        # 新文件先落盘，避免 picker 引用不到
        open(NEWFILE, "w", encoding="utf-8").write(NEW_SRC)
        open(PICKER, "w", encoding="utf-8").write(new_picker)
        note("picker rewritten, new file written")

    src = open(NEWFILE, "r", encoding="utf-8").read()
    check = bal(src)
    note("new file balance " + str(check) + " len=" + str(len(src)))
    if check != (0, 0):
        note("FAIL new file unbalanced")
        raise SystemExit(1)
    for must in ["rhPermCenter372", "RhPermissionCenterSheet", "RH_ALL_TOOLS", "McpPickerListItem("]:
        if must not in src:
            note("FAIL missing " + must)
            raise SystemExit(1)
    if src.count("LocalToolOption.") < 50:
        note("WARN tool refs=" + str(src.count("LocalToolOption.")))

    note("DONE permission center wired")
    print("::error title=rhPermCenter372::OK 权限管理面板已落地（本地工具/MCP/记忆/工作区/其他能力）")
    open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")


main()
