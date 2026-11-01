"""batch319 — wire the dsh-go chrome into ChatPage / ChatInput / ChatMessageNerdLine.

Depends on patch_batch318_dsh_chrome_file.py (RhDshChrome.kt).
Each file is edited in memory, validated, then written once (atomic).
A failure in one file never blocks the others; every outcome is reported.
"""

import os

ROOT = os.getcwd()
APP = os.path.join(ROOT, "app/src/main/java/me/rerere/rikkahub")
CHROME = os.path.join(APP, "ui/components/ai/RhDshChrome.kt")
CHAT_INPUT = os.path.join(APP, "ui/components/ai/ChatInput.kt")
CHAT_PAGE = os.path.join(APP, "ui/pages/chat/ChatPage.kt")
NERD = os.path.join(APP, "ui/components/message/ChatMessageNerdLine.kt")
DIAG = os.path.join(ROOT, "ci_diag_batch319_dsh_wiring.txt")

diag = []


def log(msg):
    print(msg)
    diag.append(str(msg))


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def mask_code(s):
    n = len(s)
    m = list(s)
    i = 0
    while i < n:
        c = s[i]
        if c == '"':
            if s.startswith('"""', i):
                j = s.find('"""', i + 3)
                end = n if j < 0 else j + 3
            else:
                k = i + 1
                while k < n:
                    if s[k] == '\\':
                        k += 2
                        continue
                    if s[k] == '"':
                        k += 1
                        break
                    k += 1
                end = k
            for x in range(i, min(end, n)):
                m[x] = ' '
            i = end
            continue
        if c == "'":
            k = i + 1
            while k < n:
                if s[k] == '\\':
                    k += 2
                    continue
                if s[k] == "'":
                    k += 1
                    break
                k += 1
            for x in range(i, min(k, n)):
                m[x] = ' '
            i = k
            continue
        if s.startswith('//', i):
            j = s.find('\n', i)
            end = n if j < 0 else j
            for x in range(i, end):
                m[x] = ' '
            i = end
            continue
        if s.startswith('/*', i):
            j = s.find('*/', i + 2)
            end = n if j < 0 else j + 2
            for x in range(i, min(end, n)):
                m[x] = ' '
            i = end
            continue
        i += 1
    return ''.join(m)


def cut_call(s, mask, start):
    i = mask.find('(', start)
    if i < 0:
        raise ValueError("no paren after " + str(start))
    depth = 0
    j = i
    while j < len(mask):
        ch = mask[j]
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                break
        j += 1
    else:
        raise ValueError("unbalanced parens from " + str(start))
    k = j + 1
    while k < len(mask) and mask[k] in ' \t\r\n':
        k += 1
    if k < len(mask) and mask[k] == '{':
        depth = 0
        j2 = k
        while j2 < len(mask):
            ch = mask[j2]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return j2 + 1
            j2 += 1
        raise ValueError("unbalanced braces from " + str(start))
    return j + 1


def balance(text):
    return text.count('{') - text.count('}'), text.count('(') - text.count(')')


ROW_TEMPLATE = r'''                    Row(
                        modifier = Modifier.fillMaxWidth(), // rhDshComposer319
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        RhDshPlusKey(
                            allowAudioVideo = allowAudioVideoAttachments,
                            onTakePicture = onTakePicture,
                            onPickImage = onPickImage,
                            onPickVideo = onPickVideo,
                            onPickAudio = onPickAudio,
                            onPickFile = onPickFile,
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(horizontal = 8.dp),
                                horizontalArrangement = Arrangement.spacedBy(4.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
__CAPS__
                            }
                        }
                        Spacer(Modifier.size(8.dp))
                        Box(modifier = Modifier.weight(1f)) {
                            TextInputRow(
                                state = state,
                                completionProviders = completionProviders,
                                onSendMessage = { sendMessage() },
                                showFullScreenButton = false,
                                showLeadingContent = false,
                            )
                        }
                        Spacer(Modifier.size(8.dp))
                        RhDshContextRing(
                            usage = rhDshUsage,
                            onClick = { rhDshUsageVisible = true },
                        )
                        Spacer(Modifier.size(2.dp))
                        if ((asrState.isAvailable || asrState.isRecording) && state.isEmpty() && !loading) {
__ASR__
                        } else {
                            RhDshSendKey(
                                loading = loading,
                                enabled = loading || !state.isEmpty(),
                                onSend = { sendMessage() },
                                onLongSend = { sendMessageWithoutAnswer() },
                            )
                        }
                    }
                    if (rhDshUsageVisible) {
                        RhDshUsageSheet(
                            usage = rhDshUsage,
                            provider = settings.providers.firstOrNull { rhProvider ->
                                rhProvider.models.any { rhModel ->
                                    rhModel.id == (conversationChatModelId ?: assistant.chatModelId ?: settings.chatModelId)
                                }
                            },
                            onDismiss = { rhDshUsageVisible = false },
                        )
                    }
'''

NEW_TOP_BAR = r'''                me.rerere.rikkahub.ui.components.ai.RhDshTopBar( // rhDshTopBar318
                    title = conversation.title.ifBlank { assistant.name },
                    statusLabel = if (loadingJob != null) "生成中" else assistant.name,
                    loading = loadingJob != null,
                    settings = setting,
                    modelId = setting.getChatModelOf(conversation)?.id,
                    previewMode = previewMode,
                    onMenuClick = { scope.launch { drawerState.open() } },
                    onNewChat = { navigateToChatPage(navController) },
                    onUpdateTitle = { vm.updateTitle(it) },
                    onImportSharedConversation = {
                        sharedConversationImportLauncher.launch(arrayOf("text/*", "application/json"))
                    },
                    onSelectModel = { vm.setChatModel(assistant = setting.getCurrentAssistant(), model = it) },
                    onTogglePreview = { previewMode = !previewMode },
                )'''

FOOTNOTE = r'''    val rhSteps = message.parts.count { it is UIMessagePart.Tool } // rhDshFootnote320
    val rhRounds = rhSteps + 1
    Text(
        text = rhSteps.toString() + " 步 · " + rhRounds.toString() + " 轮",
        style = MaterialTheme.typography.labelSmall.copy(color = color),
        modifier = modifier.padding(horizontal = 4.dp),
    )
'''


def patch_chat_input():
    src = read(CHAT_INPUT)
    before = balance(src)

    a = src.index("val enableSearchMsg = stringResource(R.string.web_search_enabled)")
    a = src.rfind("\n", 0, a) + 1
    b = src.index("if (!imeTargetVisible) {")
    b = src.rfind("\n", 0, b) + 1
    caps = src[a:b].rstrip()
    if "SearchPickerButton(" not in caps or "ReasoningButton(" not in caps:
        raise ValueError("capability block incomplete")

    mask = mask_code(src)
    asr_start = src.index("if (asrState.isAvailable || asrState.isRecording) {")
    asr_start = src.rfind("\n", 0, asr_start) + 1
    asr_end = cut_call(src, mask, asr_start)
    asr_block = src[asr_start:asr_end]
    if "AsrButton(" not in asr_block:
        raise ValueError("asr block incomplete")

    br = src.index("Row(\n                        modifier = Modifier\n                            .fillMaxWidth()\n                            .imeProgressiveCollapse(")
    br = src.rfind("\n", 0, br) + 1
    br_end = cut_call(src, mask, br)
    src = src[:br] + src[br_end:]
    log("chatinput: removed capability row " + str(br_end - br) + " chars")

    mask = mask_code(src)
    ti = src.index("TextInputRow(\n                        state = state,")
    ti = src.rfind("\n", 0, ti) + 1
    ti_end = cut_call(src, mask, ti)
    row = ROW_TEMPLATE.replace("__CAPS__", caps).replace("__ASR__", asr_block)
    src = src[:ti] + row + src[ti_end:]
    log("chatinput: composer row installed")

    anchor = "val focusManager = LocalFocusManager.current"
    i = src.index(anchor)
    i = src.index("\n", i) + 1
    src = src[:i] + "    var rhDshUsageVisible by remember { mutableStateOf(false) } // rhDshComposer319\n" + src[i:]

    sig = "    onPickFile: () -> Unit = {},\n) {"
    if src.count(sig) != 1:
        raise ValueError("signature anchor count=" + str(src.count(sig)))
    src = src.replace(
        sig,
        "    onPickFile: () -> Unit = {},\n    rhDshUsage: RhDshUsage = RhDshUsage(), // rhDshComposer319\n) {",
    )

    shape_old = """    val containerShape = if (imeVisible) {
        MaterialTheme.shapes.largeIncreased.copy(
            bottomStart = CornerSize(0.dp),
            bottomEnd = CornerSize(0.dp),
        )
    } else {
        MaterialTheme.shapes.largeIncreased
    }"""
    if shape_old not in src:
        raise ValueError("containerShape not found")
    src = src.replace(shape_old, "    val containerShape = RoundedCornerShape(28.dp) // rhDshComposer319")

    pad_old = "                .padding(horizontal = 8.dp)\n                .padding(bottom = if (imeVisible) 0.dp else 8.dp),"
    if pad_old not in src:
        raise ValueError("outer padding not found")
    src = src.replace(
        pad_old,
        "                .padding(horizontal = 12.dp) // rhDshComposer319\n                .padding(bottom = if (imeVisible) 0.dp else 8.dp),",
    )

    inner_old = "                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),"
    if inner_old not in src:
        raise ValueError("inner padding not found")
    src = src.replace(
        inner_old,
        "                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 0.dp), // rhDshComposer319",
    )

    after = balance(src)
    if after != before:
        raise ValueError("balance drift " + str(before) + " -> " + str(after))
    for must in ["RhDshPlusKey(", "RhDshContextRing(", "RhDshSendKey(", "RhDshUsageSheet(", "rhDshUsage"]:
        if must not in src:
            raise ValueError("missing " + must)
    if src.count("fun TextInputRow(") != 1:
        raise ValueError("TextInputRow definition broken")
    if "imeProgressiveCollapse(" in src and "private fun Modifier.imeProgressiveCollapse" not in src:
        raise ValueError("orphan collapse call")

    write(CHAT_INPUT, src)
    log("chatinput: OK bytes=" + str(len(src)))


def patch_chat_page():
    src = read(CHAT_PAGE)
    before = balance(src)
    mask = mask_code(src)

    anchor = "TopBar(\n                    hazeState = hazeState,"
    if src.count(anchor) != 1:
        raise ValueError("topbar call anchor count=" + str(src.count(anchor)))
    start = src.index(anchor)
    start = src.rfind("\n", 0, start) + 1
    end = cut_call(src, mask, start)
    src = src[:start] + NEW_TOP_BAR + src[end:]
    log("chatpage: top bar replaced " + str(end - start) + " chars")

    pick = "onPickFile = attachmentPickerActions.onPickFile,\n                )"
    if src.count(pick) != 1:
        raise ValueError("chatinput arg anchor count=" + str(src.count(pick)))
    src = src.replace(
        pick,
        "onPickFile = attachmentPickerActions.onPickFile,\n"
        "                    rhDshUsage = me.rerere.rikkahub.ui.components.ai.rememberRhDshUsage(\n"
        "                        conversation = conversation,\n"
        "                        modelIdentifier = currentChatModel?.modelId,\n"
        "                    ), // rhDshUsage319\n"
        "                )",
    )
    log("chatpage: composer usage wired")

    after = balance(src)
    if after != before:
        raise ValueError("balance drift " + str(before) + " -> " + str(after))
    write(CHAT_PAGE, src)
    log("chatpage: OK bytes=" + str(len(src)))


def patch_nerd():
    src = read(NERD)
    before = balance(src)
    a = src.index("    val settings = LocalSettings.current.displaySetting")
    a = src.rfind("\n", 0, a) + 1
    mask = mask_code(src)
    p = src.index("ProvideTextStyle(", a)
    b = cut_call(src, mask, p)
    src = src[:a] + FOOTNOTE + src[b:]
    after = balance(src)
    if after != before:
        raise ValueError("balance drift " + str(before) + " -> " + str(after))
    if "步 · " not in src:
        raise ValueError("footnote missing")
    write(NERD, src)
    log("nerd: footnote replaced bytes=" + str(len(src)))


def main():
    errors = []
    if not os.path.exists(CHROME):
        errors.append("chrome file missing (batch318 not applied)")

    for name, fn in (("chatinput", patch_chat_input), ("chatpage", patch_chat_page), ("nerd", patch_nerd)):
        try:
            fn()
        except Exception as exc:
            errors.append(name + " FAILED: " + str(exc))
            log(name + " FAILED: " + str(exc))

    try:
        with open(DIAG, "w", encoding="utf-8") as f:
            f.write("\n".join(diag) + "\n")
    except Exception as exc:
        print("diag fail " + str(exc))

    if errors:
        print("::error title=rhDsh319::" + " | ".join(errors))
    else:
        print("::error title=rhDsh319::OK composer+topbar+footnote wired")


main()