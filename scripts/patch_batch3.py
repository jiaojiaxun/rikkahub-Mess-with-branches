#!/usr/bin/env python3
"""Batch-3 build-time patches. Same convention as patch_batch1/2.py: anchored, idempotent,
loud (::error + exit 1 on a missing anchor), whitespace-tolerant.

1. WebDavSync list filter: accept the fork's backup names (backups were uploaded but the
   list filtered every one of them out).
2. Compaction streams the compression model's reply into CompactionPreviewStore; the
   chat loading row and the compress dialog show it.
3. Long user messages collapse (DisplaySetting fields, bubble wrapper, settings switch +
   line slider).
4. String resources for the above and for the workspace-import file picker.
"""
import glob
import re
import sys
from pathlib import Path

FAILURES = []

APP = "app/src/main/java/me/rerere/rikkahub"
WEBDAV_SYNC = f"{APP}/data/sync/webdav/WebDavSync.kt"
CHAT_SERVICE = f"{APP}/service/ChatService.kt"
CHAT_LIST = f"{APP}/ui/pages/chat/ChatList.kt"
FILES_PICKER = f"{APP}/ui/components/ai/FilesPicker.kt"
CHAT_MESSAGE = f"{APP}/ui/components/message/ChatMessage.kt"
UI_PAGE = f"{APP}/ui/pages/setting/SettingPreferencesUIPage.kt"


def fail(path, msg):
    print(f"::error file={path}::batch3 patch failed: {msg}", flush=True)
    FAILURES.append(f"{path}: {msg}")


def patch(path, marker, transform):
    p = Path(path)
    if not p.exists():
        fail(path, "file not found")
        return
    src = p.read_text(encoding="utf-8")
    if marker in src:
        print(f"already patched: {path}", flush=True)
        return
    try:
        out = transform(src)
    except Exception as e:  # report instead of a bare traceback
        fail(path, f"transform error: {e}")
        return
    if not out or out == src or marker not in out:
        fail(path, "anchor not found")
        return
    p.write_text(out, encoding="utf-8")
    print(f"patched: {path}", flush=True)


def tolerant(text):
    """Regex for `text` where every whitespace run matches any (possibly empty) whitespace."""
    parts = re.split(r"\s+", text.strip())
    return r"\s*".join(re.escape(p) for p in parts)


def match_close(src, open_index, open_ch="(", close_ch=")"):
    """Index just past the bracket matching src[open_index]; skips string literals."""
    depth = 0
    i = open_index
    in_str = False
    while i < len(src):
        c = src[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


# ------------------------------------------------------------- 1. WebDAV list filter

def t_webdav(src):
    pat = re.compile(tolerant(
        '!it.isCollection && it.displayName.startsWith("backup_") && it.displayName.endsWith(".zip")'
    ))
    if len(pat.findall(src)) != 1:
        return None
    return pat.sub(
        "!it.isCollection && me.rerere.rikkahub.data.sync.isBackupArchiveName(it.displayName)",
        src,
    )


# ------------------------------------------------------------- 2. compaction stream

COMPACTION_OLD = """val result = withTimeout(COMPACTION_REQUEST_TIMEOUT_MS) {
    providerHandler.generateText(
        providerSetting = provider,
        messages = listOf(UIMessage.user(prompt)),
        params = backgroundTextGenerationParams(model).copy(
            maxTokens = requestedTargetTokens,
        ),
    )
}
return result.message.toText().trim()
    .takeIf { it.isNotBlank() }
    ?: throw IllegalStateException("Failed to generate compressed summary")"""

COMPACTION_NEW = """// rh-batch3:compaction-stream - stream the reply so the UI can show what the
            // compression model is writing. Providers whose stream fails before any text
            // arrives fall back to the plain request.
            val compactionParams = backgroundTextGenerationParams(model).copy(
                maxTokens = requestedTargetTokens,
            )
            val previewId = kotlin.uuid.Uuid.random().toString()
            val summaryText = withTimeout(COMPACTION_REQUEST_TIMEOUT_MS) {
                var streamed = listOf(UIMessage.user(prompt))
                var streamedText = ""
                try {
                    val chunkHandler = me.rerere.ai.ui.StreamChunkHandler(model)
                    providerHandler.streamText(
                        providerSetting = provider,
                        messages = streamed,
                        params = compactionParams,
                    ).collect { chunk ->
                        streamed = chunkHandler.handle(streamed, chunk)
                        val last = streamed.last()
                        if (last.role == MessageRole.ASSISTANT) {
                            streamedText = last.toText()
                            me.rerere.rikkahub.data.ai.CompactionPreviewStore.update(
                                conversation.id, previewId, streamedText,
                            )
                        }
                    }
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Exception) {
                    if (streamedText.isNotBlank()) throw e
                    Log.w(TAG, "Compaction stream failed, retrying without streaming", e)
                } finally {
                    me.rerere.rikkahub.data.ai.CompactionPreviewStore.clear(conversation.id, previewId)
                }
                streamedText.trim().ifBlank {
                    providerHandler.generateText(
                        providerSetting = provider,
                        messages = listOf(UIMessage.user(prompt)),
                        params = compactionParams,
                    ).message.toText().trim()
                }
            }
            return summaryText
                .takeIf { it.isNotBlank() }
                ?: throw IllegalStateException("Failed to generate compressed summary")"""


def t_chat_service(src):
    pat = re.compile(tolerant(COMPACTION_OLD))
    ms = list(pat.finditer(src))
    if len(ms) != 1:
        return None
    m = ms[0]
    return src[:m.start()] + COMPACTION_NEW + src[m.end():]


def t_files_picker(src):
    pat = re.compile(r"CompressContextDialog\(\s*defaultTargetTokens")
    if len(pat.findall(src)) != 1:
        return None
    return pat.sub(
        "CompressContextDialog(\n            conversationId = conversation.id,\n            defaultTargetTokens",
        src,
    )


def t_chat_list(src):
    # The loading row (already made skin-readable by batch 2). Wrap it in a Column and show
    # the live compaction reply under it; automatic compaction runs while this row is shown.
    anchor = re.compile(r"Row\(\s*modifier = Modifier\.padding\(8\.dp\)\.rhReadableOnSkin\(\),")
    ms = list(anchor.finditer(src))
    if len(ms) != 1:
        return None
    start = ms[0].start()
    args_end = match_close(src, start + len("Row"))
    if args_end < 0:
        return None
    brace = re.compile(r"\s*\{").match(src, args_end)
    if not brace:
        return None
    body_end = match_close(src, brace.end() - 1, "{", "}")
    if body_end < 0:
        return None
    row = src[start:body_end]
    wrapped = (
        "// rh-batch3:compaction-preview\n"
        "                    androidx.compose.foundation.layout.Column {\n"
        f"                    {row}\n"
        "                    me.rerere.rikkahub.ui.components.ai.CompactionStreamPreview(\n"
        "                        conversationId = null,\n"
        "                        modifier = Modifier.padding(horizontal = 8.dp),\n"
        "                    )\n"
        "                    }"
    )
    return src[:start] + wrapped + src[body_end:]


# ------------------------------------------------------------- 3. collapse long user messages

def t_display_setting(src):
    pat = re.compile(r"data class DisplaySetting\(")
    if len(pat.findall(src)) != 1:
        return None
    return pat.sub(
        "data class DisplaySetting(\n"
        "    // rh-batch3: collapse long messages the user sent.\n"
        "    val collapseLongUserMessage: Boolean = true,\n"
        "    val collapseUserMessageLines: Int = 8,",
        src,
    )


def find_display_setting_file():
    for path in glob.glob(f"{APP}/**/*.kt", recursive=True):
        if "data class DisplaySetting(" in Path(path).read_text(encoding="utf-8"):
            return path
    return f"{APP}/data/datastore/PreferencesStore.kt"


def t_chat_message(src):
    idx = src.find("scope = AssistantAffectScope.USER")
    if idx < 0 or src.find("scope = AssistantAffectScope.USER", idx + 1) >= 0:
        return None
    start = src.rfind("MarkdownBlock(", 0, idx)
    if start < 0:
        return None
    end = match_close(src, start + len("MarkdownBlock"))
    if end < 0 or end < idx:
        return None
    block = src[start:end]
    wrapped = (
        "CollapsibleUserText(\n"
        "                                    text = part.text,\n"
        "                                    enabled = settings.displaySetting.collapseLongUserMessage,\n"
        "                                    maxLines = settings.displaySetting.collapseUserMessageLines,\n"
        "                                ) {\n"
        f"                                    {block}\n"
        "                                }"
    )
    return src[:start] + wrapped + src[end:]


UI_ITEMS = """
                    // rh-batch3: collapse long user messages
                    item(
                        headlineContent = { Text(stringResource(R.string.setting_display_page_collapse_user_message_title)) },
                        supportingContent = { Text(stringResource(R.string.setting_display_page_collapse_user_message_desc)) },
                        trailingContent = {
                            Switch(
                                checked = displaySetting.collapseLongUserMessage,
                                onCheckedChange = { updateDisplaySetting(displaySetting.copy(collapseLongUserMessage = it)) }
                            )
                        },
                    )
                    if (displaySetting.collapseLongUserMessage) {
                        item(
                            headlineContent = {
                                Text(
                                    stringResource(
                                        R.string.setting_display_page_collapse_user_message_lines,
                                        displaySetting.collapseUserMessageLines,
                                    )
                                )
                            },
                            supportingContent = {
                                Slider(
                                    value = displaySetting.collapseUserMessageLines.toFloat(),
                                    onValueChange = {
                                        updateDisplaySetting(displaySetting.copy(collapseUserMessageLines = it.roundToInt()))
                                    },
                                    valueRange = 3f..30f,
                                    steps = 26,
                                )
                            },
                        )
                    }"""


def t_ui_page(src):
    anchor = re.compile(r"updateDisplaySetting\(displaySetting\.copy\(showUserAvatar = it\)\)")
    ms = list(anchor.finditer(src))
    if len(ms) != 1:
        return None
    start = src.rfind("item(", 0, ms[0].start())
    if start < 0:
        return None
    end = match_close(src, start + len("item"))
    if end < 0:
        return None
    return src[:end] + UI_ITEMS + src[end:]


# ------------------------------------------------------------- 4. strings

STRINGS_EN = {
    "setting_display_page_collapse_user_message_title": "Collapse long user messages",
    "setting_display_page_collapse_user_message_desc": "Long messages you send are folded; tap Expand to read all",
    "setting_display_page_collapse_user_message_lines": "Fold after %d lines",
    "chat_message_expand": "Expand",
    "chat_message_collapse": "Collapse",
    "compaction_stream_title": "Compression model output",
    "chat_input_file_imported_to_workspace": "%1$s was imported to the workspace: %2$s",
    "chat_input_file_no_workspace": "%s cannot be attached. Bind a workspace to the assistant to import it",
}

STRINGS_ZH = {
    "setting_display_page_collapse_user_message_title": "折叠长用户消息",
    "setting_display_page_collapse_user_message_desc": "你发送的长消息默认折叠，点“展开全文”查看",
    "setting_display_page_collapse_user_message_lines": "超过 %d 行折叠",
    "chat_message_expand": "展开全文",
    "chat_message_collapse": "收起",
    "compaction_stream_title": "压缩模型实时输出",
    "chat_input_file_imported_to_workspace": "%1$s 已导入工作区：%2$s",
    "chat_input_file_no_workspace": "%s 无法直接发送，给助手绑定工作区后会自动导入",
}


def add_strings(path, strings):
    p = Path(path)
    src = p.read_text(encoding="utf-8")
    missing = {k: v for k, v in strings.items() if f'name="{k}"' not in src}
    if not missing:
        print(f"strings present: {path}", flush=True)
        return
    end = src.rfind("</resources>")
    if end < 0:
        fail(path, "no </resources>")
        return
    lines = "".join(
        f'    <string name="{k}" formatted="true">{v}</string>\n' for k, v in missing.items()
    )
    p.write_text(src[:end] + lines + src[end:], encoding="utf-8")
    print(f"strings added ({len(missing)}): {path}", flush=True)


def patch_strings():
    base = "app/src/main/res"
    default = f"{base}/values/strings.xml"
    if not Path(default).exists():
        fail(default, "file not found")
        return
    add_strings(default, STRINGS_EN)
    for path in glob.glob(f"{base}/values-zh*/strings.xml"):
        add_strings(path, STRINGS_ZH)


def main():
    patch(WEBDAV_SYNC, "isBackupArchiveName", t_webdav)
    patch(CHAT_SERVICE, "rh-batch3:compaction-stream", t_chat_service)
    patch(FILES_PICKER, "conversationId = conversation.id,", t_files_picker)
    patch(CHAT_LIST, "rh-batch3:compaction-preview", t_chat_list)
    patch(find_display_setting_file(), "collapseLongUserMessage", t_display_setting)
    patch(CHAT_MESSAGE, "CollapsibleUserText(", t_chat_message)
    patch(UI_PAGE, "collapseLongUserMessage", t_ui_page)
    patch_strings()
    if FAILURES:
        print("batch3 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
        return 1
    print("batch3 patches applied", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
