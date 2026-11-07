#!/usr/bin/env python3
# batch275 (Phase 4): share heart rate with the model.
#   Settings.shareHeartRateWithAI / FilesPicker badge / HeartRateDialog switch /
#   ChatVM hidden injection / ChatMessage render filter / strings.
# New file data/ble/HeartRateShareInjector.kt is committed directly.
# MARK=rhHeartRateShare
import sys
from pathlib import Path

MARK = "rhHeartRateShare"
NL = chr(10)
Q = chr(34)
DIAG = "ci_diag_batch275.txt"
applied = []
failed = []


def diag(msg):
    try:
        with open(DIAG, "a", encoding="utf-8") as f:
            f.write(msg + NL)
    except Exception:
        pass


def fail(msg):
    diag("FAIL " + msg)
    print("::error title=batch275::" + msg)
    raise SystemExit(0)


def read(path):
    p = Path(path)
    if not p.exists():
        fail("missing file: " + path)
    return p.read_text(encoding="utf-8")


def write(path, content):
    Path(path).write_text(content, encoding="utf-8")


def replace_text(content, old, new, label):
    if old not in content:
        fail(label + " text not found")
    n = content.count(old)
    if n != 1:
        fail(label + " text not unique: " + str(n))
    applied.append(label)
    return content.replace(old, new, 1)


def insert_after_line(content, anchor, block, label):
    lines = content.split(NL)
    hits = [i for i, line in enumerate(lines) if line.strip() == anchor.strip()]
    if len(hits) != 1:
        fail(label + " anchor count=" + str(len(hits)) + " [" + anchor + "]")
    lines.insert(hits[0] + 1, block)
    applied.append(label)
    return NL.join(lines)


def add_strings(path, pairs, label):
    content = read(path)
    add = []
    for name, text in pairs:
        if ("name=" + Q + name + Q) in content:
            continue
        add.append("    <string name=" + Q + name + Q + ">" + text + "</string>")
    if not add:
        diag(label + " all keys present, skip")
        return
    block = "    <!-- " + MARK + " -->" + NL + NL.join(add)
    content = replace_text(content, "</resources>", block + NL + "</resources>", label)
    write(path, content)


def edit_settings_store():
    path = "app/src/main/java/me/rerere/rikkahub/data/datastore/PreferencesStore.kt"
    content = read(path)
    if MARK in content:
        diag("preferences store already patched")
        return
    key_anchor = "        val DYNAMIC_COLOR = booleanPreferencesKey(" + Q + "dynamic_color" + Q + ")"
    key_block = "        val SHARE_HEART_RATE_WITH_AI = booleanPreferencesKey(" + Q + "share_heart_rate_with_ai" + Q + ") // " + MARK
    content = insert_after_line(content, key_anchor, key_block, "prefs-key")

    read_anchor = "                dynamicColor = preferences[DYNAMIC_COLOR] != false,"
    read_block = read_anchor + NL + "                shareHeartRateWithAI = preferences[SHARE_HEART_RATE_WITH_AI] == true, // " + MARK
    content = replace_text(content, read_anchor, read_block, "prefs-read")

    write_anchor = "            preferences[DYNAMIC_COLOR] = settings.dynamicColor"
    write_block = write_anchor + NL + "            preferences[SHARE_HEART_RATE_WITH_AI] = settings.shareHeartRateWithAI // " + MARK
    content = replace_text(content, write_anchor, write_block, "prefs-write")

    field_anchor = "    val dynamicColor: Boolean = true,"
    field_block = (
        field_anchor + NL
        + "    /** " + MARK + ": 发送消息时把当前 BLE 心率读数作为隐藏段附在 parts 首位（只给模型，不进 UI）。 */" + NL
        + "    val shareHeartRateWithAI: Boolean = false,"
    )
    content = replace_text(content, field_anchor, field_block, "prefs-field")
    write(path, content)


def edit_chat_vm():
    path = "app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatVM.kt"
    content = read(path)
    if MARK in content:
        diag("chatvm already patched")
        return
    anchor = "        if (content.isEmptyInputMessage()) return"
    block = (
        "        // " + MARK + ": 心率隐藏段（首位）。开关/连接/读数在注入器里判定，开关关闭时零改动。" + NL
        + "        val rhContent = me.rerere.rikkahub.data.ble.HeartRateShareInjector" + NL
        + "            .maybePrepend(settingsStore, content)"
    )
    content = insert_after_line(content, anchor, block, "chatvm-inject")
    old_send = "            chatService.sendMessage(_conversationId, content, false, quotedMessageId)"
    new_send = "            chatService.sendMessage(_conversationId, rhContent, false, quotedMessageId)"
    content = replace_text(content, old_send, new_send, "chatvm-answer-false")
    old_queue = "        pendingMessages.add(PendingSend(content, quotedMessageId)) // rhQuoteQueue250"
    new_queue = "        pendingMessages.add(PendingSend(rhContent, quotedMessageId)) // rhQuoteQueue250"
    content = replace_text(content, old_queue, new_queue, "chatvm-queue")
    write(path, content)


def edit_chat_message():
    path = "app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt"
    content = read(path)
    if MARK in content:
        diag("chatmessage already patched")
        return
    old = (
        "            MessagePartsBlock(" + NL
        + "                assistant = assistant," + NL
        + "                role = message.role," + NL
        + "                parts = message.parts,"
    )
    new = (
        "            MessagePartsBlock(" + NL
        + "                assistant = assistant," + NL
        + "                role = message.role," + NL
        + "                // " + MARK + ": 隐藏注入段（心率）只给模型看，不进 UI" + NL
        + "                parts = message.parts.filterNot {" + NL
        + "                    me.rerere.rikkahub.data.ble.HeartRateShareInjector.isHiddenPart(it)" + NL
        + "                },"
    )
    content = replace_text(content, old, new, "chatmessage-filter")
    write(path, content)


def edit_files_picker():
    path = "app/src/main/java/me/rerere/rikkahub/ui/components/ai/FilesPicker.kt"
    content = read(path)
    if MARK in content:
        diag("filespicker already patched")
        return
    imp_anchor = "import me.rerere.rikkahub.data.datastore.Settings"
    content = insert_after_line(
        content, imp_anchor,
        "import me.rerere.rikkahub.data.ble.HeartRateMonitor // " + MARK,
        "filespicker-import",
    )
    old = (
        "            headlineContent = {" + NL
        + "                Text(stringResource(R.string.heart_rate_title))" + NL
        + "            },"
    )
    new = (
        old + NL
        + "            trailingContent = {" + NL
        + "                // " + MARK + ": 连接状态角标（实时）" + NL
        + "                val rhHeartRate by HeartRateMonitor.state.collectAsState()" + NL
        + "                Text(" + NL
        + "                    text = if (rhHeartRate.connected && rhHeartRate.bpm != null) {" + NL
        + "                        stringResource(R.string.heart_rate_connected_badge, rhHeartRate.bpm ?: 0)" + NL
        + "                    } else {" + NL
        + "                        stringResource(R.string.heart_rate_disconnected_badge)" + NL
        + "                    }," + NL
        + "                    style = MaterialTheme.typography.labelSmall," + NL
        + "                    color = MaterialTheme.colorScheme.onSurfaceVariant," + NL
        + "                )" + NL
        + "            },"
    )
    content = replace_text(content, old, new, "filespicker-badge")
    write(path, content)


def edit_heart_rate_dialog():
    path = "app/src/main/java/me/rerere/rikkahub/ui/components/ai/HeartRateDialog.kt"
    content = read(path)
    if MARK in content:
        diag("heartrate dialog already patched")
        return
    content = insert_after_line(content, "import androidx.compose.runtime.remember",
                                "import androidx.compose.runtime.rememberCoroutineScope // " + MARK, "hr-import-scope")
    content = insert_after_line(content, "import androidx.compose.material3.TextButton",
                                "import androidx.compose.material3.Switch // " + MARK, "hr-import-switch")
    content = insert_after_line(content, "import me.rerere.rikkahub.data.ble.HeartRateMonitor",
                                "import me.rerere.rikkahub.data.datastore.Settings // " + MARK + NL
                                + "import me.rerere.rikkahub.data.datastore.SettingsStore // " + MARK + NL
                                + "import kotlinx.coroutines.launch // " + MARK + NL
                                + "import org.koin.compose.koinInject // " + MARK, "hr-imports")

    old = (
        "                state.error?.let { error ->" + NL
        + "                    Text(" + NL
        + "                        text = error," + NL
        + "                        style = MaterialTheme.typography.bodySmall," + NL
        + "                        color = MaterialTheme.colorScheme.error," + NL
        + "                    )" + NL
        + "                }"
    )
    new = (
        old + NL
        + "" + NL
        + "                // " + MARK + ": 是否把心率附在发送的消息里（持久设置）" + NL
        + "                val rhSettingsStore: SettingsStore = koinInject()" + NL
        + "                val rhSettings by rhSettingsStore.settingsFlow.collectAsStateWithLifecycle(" + NL
        + "                    initialValue = Settings.dummy()" + NL
        + "                )" + NL
        + "                val rhShareScope = rememberCoroutineScope()" + NL
        + "                Row(" + NL
        + "                    modifier = Modifier.fillMaxWidth()," + NL
        + "                    verticalAlignment = Alignment.CenterVertically," + NL
        + "                    horizontalArrangement = Arrangement.SpaceBetween," + NL
        + "                ) {" + NL
        + "                    Text(" + NL
        + "                        text = stringResource(R.string.heart_rate_share_with_ai)," + NL
        + "                        style = MaterialTheme.typography.bodySmall," + NL
        + "                    )" + NL
        + "                    Switch(" + NL
        + "                        checked = rhSettings.shareHeartRateWithAI," + NL
        + "                        onCheckedChange = { checked ->" + NL
        + "                            rhShareScope.launch {" + NL
        + "                                rhSettingsStore.update { old -> old.copy(shareHeartRateWithAI = checked) }" + NL
        + "                            }" + NL
        + "                        }," + NL
        + "                    )" + NL
        + "                }"
    )
    content = replace_text(content, old, new, "hr-switch")
    write(path, content)


def main():
    for label, fn in (
        ("settings-store", edit_settings_store),
        ("chat-vm", edit_chat_vm),
        ("chat-message", edit_chat_message),
        ("files-picker", edit_files_picker),
        ("heart-rate-dialog", edit_heart_rate_dialog),
    ):
        try:
            fn()
        except SystemExit:
            failed.append(label)
        except Exception as e:
            diag("EXCEPTION " + label + ": " + repr(e))
            failed.append(label)
    try:
        add_strings(
            "app/src/main/res/values/strings.xml",
            [
                ("heart_rate_connected_badge", "Connected: %1$d/min"),
                ("heart_rate_disconnected_badge", "Not connected"),
                ("heart_rate_share_with_ai", "Attach heart rate to messages"),
            ],
            "strings-en",
        )
        add_strings(
            "app/src/main/res/values-zh/strings.xml",
            [
                ("heart_rate_connected_badge", "已连接：%1$d/min"),
                ("heart_rate_disconnected_badge", "未连接"),
                ("heart_rate_share_with_ai", "发送消息时附带心率"),
            ],
            "strings-zh",
        )
    except SystemExit:
        failed.append("strings")
    except Exception as e:
        diag("EXCEPTION strings: " + repr(e))
        failed.append("strings")
    diag("applied=" + str(len(applied)) + " failed=" + str(len(failed)))
    if applied:
        print("::notice title=batch275-applied::" + ",".join(applied))
    if failed:
        print("::error title=batch275-FAILED::" + ",".join(failed))


main()
