#!/usr/bin/env python3
"""Batch-1 build-time patches (branch fix/batch1).

Same convention as the other scripts/patch_*.py: anchored, idempotent (a marker makes a
second run a no-op) and loud: an anchor that does not match becomes a ::error annotation
and the script exits 1. Regexes tolerate whitespace differences.
"""
import re
import sys
from pathlib import Path

FAILURES = []

PROVIDER_SETTING = "ai/src/main/java/me/rerere/ai/provider/ProviderSetting.kt"
RESPONSE_API = "ai/src/main/java/me/rerere/ai/provider/providers/openai/ResponseAPI.kt"
CHAT_COMPLETIONS = "ai/src/main/java/me/rerere/ai/provider/providers/openai/ChatCompletionsAPI.kt"
PROVIDER_CONFIGURE = "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/components/ProviderConfigure.kt"
CHAT_MESSAGE_TOOLS = "app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageTools.kt"
CHAT_PAGE = "app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt"
CHAT_UI_TOOLS = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/local/ChatUiTools.kt"


def fail(path, msg):
    print(f"::error file={path}::batch1 patch failed: {msg}", flush=True)
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
    out = transform(src)
    if not out or out == src:
        fail(path, "anchor not found")
        return
    if marker not in out:
        fail(path, "marker missing after transform")
        return
    p.write_text(out, encoding="utf-8")
    print(f"patched: {path}", flush=True)


# 1. responsesPath (upstream 2.5.0 a61d116d)

def t_provider_setting(src):
    cls = src.find("data class OpenAI(")
    if cls < 0:
        return None
    m = re.compile(r"\n([ \t]*)var includeHistoryReasoning: Boolean = true,").search(src, cls)
    if not m:
        return None
    ind = m.group(1)
    ins = ("\n" + ind + "// rh-batch1:responses-path (upstream 2.5.0 a61d116d)"
           "\n" + ind + 'var responsesPath: String = "/responses",')
    return src[:m.end()] + ins + src[m.end():]


def t_response_api(src):
    old = '"${providerSetting.baseUrl}/responses"'
    if src.count(old) != 2:
        return None
    new = '"${providerSetting.baseUrl}${providerSetting.responsesPath.ifBlank { "/responses" }}"'
    src = src.replace(old, new)
    tag = 'private const val TAG = "ResponseAPI"'
    if tag not in src:
        return None
    return src.replace(tag, "// rh-batch1:responses-path\n" + tag, 1)


PATH_FIELD = """// rh-batch1:responses-path - one path field that edits whichever API is active
    OutlinedTextField(
        value = if (provider.useResponseApi) provider.responsesPath else provider.chatCompletionsPath,
        onValueChange = {
            val path = it.trim()
            onEdit(
                if (provider.useResponseApi) provider.copy(responsesPath = path)
                else provider.copy(chatCompletionsPath = path)
            )
        },
        label = { Text(stringResource(R.string.setting_provider_page_api_path)) },
        placeholder = { Text(if (provider.useResponseApi) "/responses" else "/chat/completions") },
        modifier = Modifier.fillMaxWidth(),
        enabled = !provider.builtIn,
    )"""


def t_provider_configure(src):
    pat = re.compile(
        r"if \(!provider\.useResponseApi\) \{\s*"
        r"OutlinedTextField\(\s*"
        r"value = provider\.chatCompletionsPath,\s*"
        r"onValueChange = \{ onEdit\(provider\.copy\(chatCompletionsPath = it\.trim\(\)\)\) \},\s*"
        r"label = \{ Text\(stringResource\(R\.string\.setting_provider_page_api_path\)\) \},\s*"
        r"modifier = Modifier\.fillMaxWidth\(\),\s*"
        r"enabled = !provider\.builtIn,\s*"
        r"\)\s*\}"
    )
    ms = list(pat.finditer(src))
    if len(ms) != 1:
        return None
    m = ms[0]
    return src[:m.start()] + PATH_FIELD + src[m.end():]


# 2. reasoning OFF without REASONING flag

HOSTS_DECL = """// rh-batch1:reasoning-off - hosts whose branch in buildChatCompletionRequest sends an
// explicit disable switch (thinking.type=disabled / enable_thinking=false /
// thinking_mode=false) that non-thinking models accept too. Generic OpenAI-compatible
// hosts are excluded: an unknown server may reject reasoning_effort for a model without
// reasoning support. DashScope is excluded because its branch sends reasoning_effort.
private val RH_THINKING_DISABLE_HOSTS = setOf(
    "api.deepseek.com",
    "ark.cn-beijing.volces.com",
    "open.bigmodel.cn",
    "api.moonshot.cn",
    "api.siliconflow.cn",
    "aiping.cn",
    "chat.intern-ai.org.cn",
)

"""

GATE = """// rh-batch1:reasoning-off - OFF must also reach hosts that think by default when the
            // model has no REASONING flag (e.g. manually added Qwen3 / DeepSeek).
            val rhHasReasoning = params.model.abilities.contains(ModelAbility.REASONING)
            val rhForceOff = !rhHasReasoning && params.reasoningLevel == ReasoningLevel.OFF &&
                host in RH_THINKING_DISABLE_HOSTS
            if (rhHasReasoning || rhForceOff) {"""


def t_chat_completions(src):
    gate = re.compile(
        r"if \(params\.model\.abilities\.contains\(ModelAbility\.REASONING\)\) \{"
        r"(?=\s*val level = params\.reasoningLevel\s*when \(host\))"
    )
    ms = list(gate.finditer(src))
    if len(ms) != 1:
        return None
    m = ms[0]
    src = src[:m.start()] + GATE + src[m.end():]
    cls = "class ChatCompletionsAPI("
    if src.count(cls) != 1:
        return None
    return src.replace(cls, HOSTS_DECL + cls, 1)


# 3. two-button approval

APPROVAL_IMPORTS = """import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
"""

APPROVAL_CALL = """ToolApprovalButtons(
                            enabled = !inFlight,
                            allowAlways = allowAlwaysButton,
                            onAllowOnce = {
                                inFlight = true
                                onToolApproval(
                                    tool.toolCallId, true, "",
                                    me.rerere.rikkahub.service.ChatService.ApprovalScope.Once,
                                    tool.toolName,
                                )
                            },
                            onAllowChat = {
                                inFlight = true
                                onToolApproval(
                                    tool.toolCallId, true, "",
                                    me.rerere.rikkahub.service.ChatService.ApprovalScope.ChatScope,
                                    tool.toolName,
                                )
                            },
                            onAllowAlways = {
                                inFlight = true
                                onToolApproval(
                                    tool.toolCallId, true, "",
                                    me.rerere.rikkahub.service.ChatService.ApprovalScope.Always,
                                    tool.toolName,
                                )
                            },
                            onDeny = {
                                inFlight = true
                                onToolApproval(
                                    tool.toolCallId, false, "",
                                    me.rerere.rikkahub.service.ChatService.ApprovalScope.Once,
                                    tool.toolName,
                                )
                            },
                            onDenyWithReason = { showDenyDialog = true },
                        )"""

APPROVAL_COMPOSABLES = """
// rh-batch1:approval - large two-button approval row.
// Tap Allow = allow once; long-press Allow = "allow for this chat" / "always allow"
// (unless the tool forbids it). Tap Deny = deny; long-press Deny = deny with a reason.
@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun ToolApprovalButtons(
    enabled: Boolean,
    allowAlways: Boolean,
    onAllowOnce: () -> Unit,
    onAllowChat: () -> Unit,
    onAllowAlways: () -> Unit,
    onDeny: () -> Unit,
    onDenyWithReason: () -> Unit,
) {
    var showScopes by remember { mutableStateOf(false) }
    Column(
        verticalArrangement = Arrangement.spacedBy(6.dp),
        modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
    ) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Box(modifier = Modifier.weight(1f)) {
                ApprovalBigButton(
                    label = stringResource(R.string.chat_message_tool_approve),
                    icon = HugeIcons.Tick01,
                    container = MaterialTheme.colorScheme.primary,
                    content = MaterialTheme.colorScheme.onPrimary,
                    enabled = enabled,
                    onClick = onAllowOnce,
                    onLongClick = { showScopes = true },
                )
                DropdownMenu(
                    expanded = showScopes,
                    onDismissRequest = { showScopes = false },
                ) {
                    DropdownMenuItem(
                        text = { Text(stringResource(R.string.chat_tool_approval_allow_chat)) },
                        onClick = {
                            showScopes = false
                            onAllowChat()
                        },
                    )
                    if (allowAlways) {
                        DropdownMenuItem(
                            text = { Text(stringResource(R.string.chat_tool_approval_allow_always)) },
                            onClick = {
                                showScopes = false
                                onAllowAlways()
                            },
                        )
                    }
                }
            }
            ApprovalBigButton(
                label = stringResource(R.string.chat_message_tool_deny),
                icon = HugeIcons.Cancel01,
                container = MaterialTheme.colorScheme.errorContainer,
                content = MaterialTheme.colorScheme.onErrorContainer,
                enabled = enabled,
                onClick = onDeny,
                onLongClick = onDenyWithReason,
                modifier = Modifier.weight(1f),
            )
        }
        Text(
            text = stringResource(R.string.chat_tool_approval_hint),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun ApprovalBigButton(
    label: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    container: Color,
    content: Color,
    enabled: Boolean,
    onClick: () -> Unit,
    onLongClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val shape = RoundedCornerShape(14.dp)
    Row(
        modifier = modifier
            .fillMaxWidth()
            .heightIn(min = 52.dp)
            .clip(shape)
            .background(if (enabled) container else container.copy(alpha = 0.4f))
            .combinedClickable(
                enabled = enabled,
                role = Role.Button,
                onClick = onClick,
                onLongClick = onLongClick,
            )
            .padding(horizontal = 12.dp, vertical = 10.dp),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = content,
            modifier = Modifier.size(20.dp),
        )
        Text(
            text = label,
            color = content,
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.padding(start = 8.dp),
        )
    }
}
"""


def t_chat_message_tools(src):
    c = src.find("// Four-button row")
    if c < 0:
        return None
    line_end = src.find("\n", c)
    src = src[:c] + "// rh-batch1:approval - two large buttons; scopes and deny reason via long-press." + src[line_end:]
    m = re.compile(
        r"Row\(\s*horizontalArrangement\s*=\s*Arrangement\.spacedBy\(6\.dp\)\s*\)\s*\{"
    ).search(src, c)
    if not m:
        return None
    start = m.start()
    depth = 0
    end = -1
    for j in range(m.end() - 1, len(src)):
        ch = src[j]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = j + 1
                break
    if end < 0:
        return None
    block = src[start:end]
    if "ApprovalScope.ChatScope" not in block or "showDenyDialog = true" not in block:
        return None
    src = src[:start] + APPROVAL_CALL + src[end:]
    anchor = "import androidx.compose.foundation.layout.Arrangement\n"
    if anchor not in src:
        return None
    src = src.replace(anchor, APPROVAL_IMPORTS + anchor, 1)
    return src.rstrip() + "\n" + APPROVAL_COMPOSABLES


# 4. Native UI button in the top bar

NATIVE_EXIT = """
            // rh-batch1:native-exit - one tap back to the native chat UI while an HTML skin
            // is on (the skin file stays; the AI can switch it back with chat_ui_set_mode).
            if (me.rerere.rikkahub.data.ai.tools.local.ChatHtmlSkinGlobal.isReady) {
                val rhSkinState by me.rerere.rikkahub.data.ai.tools.local.ChatHtmlSkinGlobal.store
                    .stateFlow.collectAsStateWithLifecycle()
                if (rhSkinState.htmlModeEnabled) {
                    androidx.compose.material3.FilledTonalButton(
                        onClick = {
                            me.rerere.rikkahub.data.ai.tools.local.ChatHtmlSkinGlobal.store.setMode(false)
                        },
                        contentPadding = androidx.compose.foundation.layout.PaddingValues(
                            horizontal = 12.dp,
                            vertical = 4.dp,
                        ),
                    ) {
                        Text(
                            text = stringResource(R.string.chat_html_exit_native),
                            style = MaterialTheme.typography.labelLarge,
                        )
                    }
                }
            }"""


def t_chat_page(src):
    ms = list(re.compile(r"actions = \{(?=\s*var showShareMenu by remember)").finditer(src))
    if len(ms) != 1:
        return None
    m = ms[0]
    return src[:m.end()] + NATIVE_EXIT + src[m.end():]


# 5. tell the model about the safe area

SKIN_DOC = (
    "Layout: the native top bar and input bar are drawn over the skin; CSS variables "
    "--rh-safe-top / --rh-safe-bottom (px) hold their heights and body is padded by them, "
    "so keep buttons and widgets inside that safe area. Theme colors: --rh-primary, "
    "--rh-on-primary, --rh-surface, --rh-on-surface, --rh-background, --rh-on-background. "
    "Low-contrast buttons/links are auto-corrected (opt out with data-rh-contrast=\\\"off\\\"); "
    "fixed widgets overlapping the native bars are moved (opt out with data-rh-safe=\\\"off\\\"). "
)


def t_chat_ui_tools(src):
    anchor = "Writes need user approval; explain the design in `reason`."
    if src.count(anchor) != 1:
        return None
    return src.replace(anchor, SKIN_DOC + anchor, 1)


# 6. strings

STRINGS_EN = """    <!-- rh-batch1 -->
    <string name="chat_tool_approval_allow_chat">Allow for this chat</string>
    <string name="chat_tool_approval_allow_always">Always allow</string>
    <string name="chat_tool_approval_hint">Long-press Allow for more options. Long-press Deny to give a reason.</string>
    <string name="chat_html_exit_native">Native UI</string>
"""

STRINGS_ZH = """    <!-- rh-batch1 -->
    <string name="chat_tool_approval_allow_chat">本对话内允许</string>
    <string name="chat_tool_approval_allow_always">始终允许</string>
    <string name="chat_tool_approval_hint">长按「允许」可选择范围，长按「拒绝」可填写原因</string>
    <string name="chat_html_exit_native">恢复原生</string>
"""


def patch_strings():
    res = Path("app/src/main/res")
    files = sorted(res.glob("values*/strings.xml"))
    if not any(f.parent.name == "values" for f in files):
        fail(str(res), "values/strings.xml not found")
        return
    for f in files:
        block = STRINGS_ZH if f.parent.name.startswith("values-zh") else STRINGS_EN

        def add(s, b=block):
            i = s.rfind("</resources>")
            return None if i < 0 else s[:i] + b + s[i:]

        patch(str(f), "rh-batch1", add)


def main():
    patch(PROVIDER_SETTING, "rh-batch1:responses-path", t_provider_setting)
    patch(RESPONSE_API, "rh-batch1:responses-path", t_response_api)
    patch(PROVIDER_CONFIGURE, "rh-batch1:responses-path", t_provider_configure)
    patch(CHAT_COMPLETIONS, "rh-batch1:reasoning-off", t_chat_completions)
    patch(CHAT_MESSAGE_TOOLS, "rh-batch1:approval", t_chat_message_tools)
    patch(CHAT_PAGE, "rh-batch1:native-exit", t_chat_page)
    patch(CHAT_UI_TOOLS, "--rh-safe-top", t_chat_ui_tools)
    patch_strings()
    if FAILURES:
        print("batch1 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
        return 1
    print("batch1 patches applied", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
