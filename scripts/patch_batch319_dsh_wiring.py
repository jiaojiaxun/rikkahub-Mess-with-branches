"""batch319 v2 — wire the dsh-go chrome into ChatPage / ChatInput / ChatMessageNerdLine.

v1 (run#560) root cause, proven by ci_diag:
  the capability block was cut from "val enableSearchMsg" up to the line
  "if (!imeTargetVisible)" — that slice also carried the closing brace of the
  inner scrollable Row, so the slice itself was brace-negative (-1). Inserting
  it elsewhere made the whole file -1 and the atomic guard refused to write.
  Result: ChatInput untouched, and batch320 then found no anchor.

v2 fixes that by trimming trailing standalone "}" lines until the slice is
balanced, asserts balance for every slice, and prints every measurement.

Depends on patch_batch318_dsh_chrome_file.py (RhDshChrome.kt).
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


def log(m):
    print(m)
    diag.append(str(m))


def read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def write(p, s):
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)


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


def balance(t):
    return t.count('{') - t.count('}'), t.count('(') - t.count(')')


def trim_trailing_closers(block):
    """Drop trailing standalone '}' lines until the slice is brace-balanced."""
    text = block.rstrip()
    guard = 0
    while balance(text)[0] < 0 and guard < 8:
        lines = text.split('\n')
        dropped = False
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip() == '}':
                del lines[i]
                dropped = True
                break
        if not dropped:
            break
        text = '\n'.join(lines).rstrip()
        guard += 1
    return text


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
                    onMenuClick = { __SCOPE__.launch { drawerState.open() } },
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

    # capability block: from enableSearchMsg up to the "more" guard
    a = src.index("val enableSearchMsg = stringResource(R.string.web_search_enabled)")
    a = src.rfind("\n", 0, a) + 1
    b = src.index("if (!imeTargetVisible) {")
    b = src.rfind("\n", 0, b) + 1
    caps = trim_trailing_closers(src[a:b])
    caps_bal = balance(caps)
    log("chatinput: caps balance=" + str(caps_bal) + " len=" + str(len(caps)))
    if caps_bal != (0, 0):
        raise ValueError("caps still unbalanced " + str(caps_bal))
    if "SearchPickerButton(" not in caps or "ReasoningButton(" not in caps:
        raise ValueError("capability block incomplete")

    mask = mask_code(src)
    asr_start = src.index("if (asrState.isAvailable || asrState.isRecording) {")
    asr_start = src.rfind("\n", 0, asr_start) + 1
    asr_end = cut_call(src, mask, asr_start)
    asr_block = src[asr_start:asr_end]
    asr_bal = balance(asr_block)
    log("chatinput: asr balance=" + str(asr_bal) + " len=" + str(len(asr_block)))
    if asr_bal != (0, 0) or "AsrButton(" not in asr_block:
        raise ValueError("asr block bad " + str(asr_bal))

    # delete the old capability row (re-hosted in the + menu)
    br = src.index("Row(\n                        modifier = Modifier\n                            .fillMaxWidth()\n                            .imeProgressiveCollapse(")
    br = src.rfind("\n", 0, br) + 1
    br_end = cut_call(src, mask, br)
    deleted = src[br:br_end]
    del_bal = balance(deleted)
    log("chatinput: deleted row balance=" + str(del_bal) + " len=" + str(len(deleted)))
    if del_bal != (0, 0):
        raise ValueError("deleted row unbalanced " + str(del_bal))
    src = src[:br] + src[br_end:]

    # replace the TextInputRow call with the single-row composer
    mask = mask_code(src)
    ti = src.index("TextInputRow(\n                        state = state,")
    ti = src.rfind("\n", 0, ti) + 1
    ti_end = cut_call(src, mask, ti)
    if balance(src[ti:ti_end]) != (0, 0):
        raise ValueError("TextInputRow call unbalanced")
    row = ROW_TEMPLATE.replace("__CAPS__", caps).replace("__ASR__", asr_block)
    row_bal = balance(row)
    log("chatinput: row balance=" + str(row_bal))
    if row_bal != (0, 0):
        raise ValueError("row template unbalanced " + str(row_bal))
    src = src[:ti] + row + src[ti_end:]

    # usage-sheet visibility state
    anchor = "val focusManager = LocalFocusManager.current"
    i = src.index(anchor)
    i = src.index("\n", i) + 1
    src = src[:i] + "    var rhDshUsageVisible by remember { mutableStateOf(false) } // rhDshComposer319\n" + src[i:]

    # new parameter
    sig = "    onPickFile: () -> Unit = {},\n) {"
    if src.count(sig) != 1:
        raise ValueError("signature anchor count=" + str(src.count(sig)))
    src = src.replace(
        sig,
        "    onPickFile: () -> Unit = {},\n    rhDshUsage: RhDshUsage = RhDshUsage(), // rhDshComposer319\n) {",
    )

    # 28dp card + edge-to-edge keys
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
    log("chatinput: final balance " + str(before) + " -> " + str(after))
    if after != before:
        raise ValueError("balance drift " + str(before) + " -> " + str(after))
    for must in ["RhDshPlusKey(", "RhDshContextRing(", "RhDshSendKey(", "RhDshUsageSheet(", "rhDshUsage"]:
        if must not in src:
            raise ValueError("missing " + must)
    if src.count("fun TextInputRow(") != 1:
        raise ValueError("TextInputRow definition broken")

    write(CHAT_INPUT, src)
    log("chatinput: OK bytes=" + str(len(src)))


def patch_chat_page():
    src = read(CHAT_PAGE)
    before = balance(src)
    scope_expr = "scope"

    top = "            topBar = {"
    if src.count(top) == 1:
        src = src.replace(
            top,
            "            topBar = {\n                val rhDshTopScope = androidx.compose.runtime.rememberCoroutineScope() // rhDsh319",
        )
        scope_expr = "rhDshTopScope"
        log("chatpage: local top-bar scope added")
    else:
        log("chatpage: topBar anchor count=" + str(src.count(top)) + " -> reuse outer scope")

    mask = mask_code(src)
    anchor = "TopBar(\n                    hazeState = hazeState,"
    if src.count(anchor) != 1:
        raise ValueError("topbar call anchor count=" + str(src.count(anchor)))
    start = src.index(anchor)
    start = src.rfind("\n", 0, start) + 1
    end = cut_call(src, mask, start)
    src = src[:start] + NEW_TOP_BAR.replace("__SCOPE__", scope_expr) + src[end:]
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
    log("chatpage: balance " + str(before) + " -> " + str(after))
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
    log("nerd: balance " + str(before) + " -> " + str(after))
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
        print("::error title=rhDsh319::OK composer+topbar+footnote wired (v2)")


main()