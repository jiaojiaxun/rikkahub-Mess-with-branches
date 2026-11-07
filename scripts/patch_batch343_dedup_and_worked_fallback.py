"""batch343 — 两处去重/兜底。

A) ＋ 菜单的能力行与「文件与工具」面板重复
   batch326 已把 FilesPicker 顶部三个附件按钮换成「联网搜索 / 思考深度」，
   但 ＋ 菜单里还留着同一对图标（batch319 搬进去的 caps）。两处指向同一功能。
   本批把 ＋ 菜单的 trailing capability 行去掉：附件留在 ＋ 菜单，
   搜索/思考统一在「文件与工具」面板。

B) 收尾时长兜底
   rhStepsEndMillis 只取 reasoning.finishedAt；一条只有工具步（或 reasoning 未写
   finishedAt）的旧消息算不出时长，header 于是回退到「正在处理…」——正是用户抱怨
   的状态。把 tool.executionStartedAt 也作为结束时间候选（它已是 Long），
   让更多已完成消息能落到「已工作 x」。

Python 侧：所有锚点唯一，逐文件独立 try，写盘前做括号差值校验。
"""

import os

ROOT = os.getcwd()
CHROME = os.path.join(
    ROOT, "app/src/main/java/me/rerere/rikkahub/ui/components/ai/RhDshChrome.kt"
)
CHAT_INPUT = os.path.join(
    ROOT, "app/src/main/java/me/rerere/rikkahub/ui/components/ai/ChatInput.kt"
)
DRAWER = os.path.join(
    ROOT, "app/src/main/java/me/rerere/rikkahub/ui/components/message/RhThoughtDrawer.kt"
)
DIAG = os.path.join(ROOT, "ci_diag_batch343_dedup.txt")

log = []


def note(m):
    print(m)
    log.append(str(m))


def bal(t):
    return (t.count('{') - t.count('}'), t.count('(') - t.count(')'))


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
        i += 1
    return ''.join(m)


def find_close(mask, start, open_ch, close_ch):
    depth = 0
    i = start
    while i < len(mask):
        ch = mask[i]
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError("unbalanced " + open_ch)


def fix_chrome():
    src = read(CHROME)
    before = bal(src)

    sig_old = "    capabilities: @Composable () -> Unit,\n) {"
    sig_new = "    capabilities: (@Composable () -> Unit)? = null,\n) {"
    if src.count(sig_old) != 1:
        raise ValueError("capabilities signature count=" + str(src.count(sig_old)))
    src = src.replace(sig_old, sig_new)

    row_old = (
        "            Row(\n"
        "                modifier = Modifier\n"
        "                    .fillMaxWidth()\n"
        "                    .padding(horizontal = 8.dp, vertical = 4.dp),\n"
        "                horizontalArrangement = Arrangement.spacedBy(4.dp),\n"
        "                verticalAlignment = Alignment.CenterVertically,\n"
        "            ) {\n"
        "                capabilities()\n"
        "            }"
    )
    row_new = (
        "            val caps = capabilities // rh343: 能力入口统一到「文件与工具」面板\n"
        "            if (caps != null) {\n"
        "                Row(\n"
        "                    modifier = Modifier\n"
        "                        .fillMaxWidth()\n"
        "                        .padding(horizontal = 8.dp, vertical = 4.dp),\n"
        "                    horizontalArrangement = Arrangement.spacedBy(4.dp),\n"
        "                    verticalAlignment = Alignment.CenterVertically,\n"
        "                ) {\n"
        "                    caps()\n"
        "                }\n"
        "            }"
    )
    if src.count(row_old) != 1:
        raise ValueError("capability row count=" + str(src.count(row_old)))
    src = src.replace(row_old, row_new)

    after = bal(src)
    note("chrome: balance " + str(before) + " -> " + str(after))
    if after != before:
        raise ValueError("balance drift")
    write(CHROME, src)
    note("chrome: capability row now optional")


def fix_chat_input():
    src = read(CHAT_INPUT)
    before = bal(src)
    mask = mask_code(src)

    start = src.index("RhDshPlusKey(")
    paren = mask.find("(", start)
    paren_end = find_close(mask, paren, "(", ")")
    brace = mask.find("{", paren_end + 1)
    if brace < 0 or brace - paren_end > 4:
        raise ValueError("no trailing lambda")
    brace_end = find_close(mask, brace, "{", "}")

    removed = src[brace : brace_end + 1]
    note("chatinput: trailing lambda size=" + str(len(removed)))
    src = src[:brace] + src[brace_end + 1 :]

    # 收尾：把 ")" 后残留的空行压掉一行
    src = src.replace("                        )\n\n                        Spacer(Modifier.size(8.dp))", "                        )\n                        Spacer(Modifier.size(8.dp))")

    after = bal(src)
    note("chatinput: balance " + str(before) + " -> " + str(after))
    if after != before:
        raise ValueError("balance drift")
    if "SearchPickerButton(" in src and "ReasoningButton(" in src:
        raise ValueError("capabilities still referenced")
    write(CHAT_INPUT, src)
    note("chatinput: ＋ menu carries attachments + 文件与工具 only")


def fix_drawer_end():
    src = read(DRAWER)
    before = bal(src)
    old = (
        "private fun rhStepsEndMillis(steps: List<ThinkingStep>): Long? {\n"
        "    return steps.filterIsInstance<ThinkingStep.ReasoningStep>()\n"
        "        .mapNotNull { it.reasoning.finishedAt?.toEpochMilliseconds() }\n"
        "        .maxOrNull()\n"
        "}"
    )
    new = (
        "private fun rhStepsEndMillis(steps: List<ThinkingStep>): Long? { // rh343\n"
        "    val candidates = mutableListOf<Long>()\n"
        "    steps.filterIsInstance<ThinkingStep.ReasoningStep>().forEach { step ->\n"
        "        step.reasoning.finishedAt?.toEpochMilliseconds()?.let { candidates.add(it) }\n"
        "    }\n"
        "    steps.filterIsInstance<ThinkingStep.ToolStep>().forEach { step ->\n"
        "        step.tool.executionStartedAt?.let { candidates.add(it) }\n"
        "    }\n"
        "    return candidates.maxOrNull()\n"
        "}"
    )
    if src.count(old) != 1:
        raise ValueError("end millis anchor count=" + str(src.count(old)))
    src = src.replace(old, new)
    after = bal(src)
    note("drawer: balance " + str(before) + " -> " + str(after))
    if after != before:
        raise ValueError("balance drift")
    write(DRAWER, src)
    note("drawer: end time also considers tool start")


def main():
    errors = []
    for name, fn in (("chrome", fix_chrome), ("chatinput", fix_chat_input), ("drawer", fix_drawer_end)):
        try:
            fn()
        except Exception as exc:
            errors.append(name + " FAILED: " + str(exc))
            note(name + " FAILED: " + str(exc))

    open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
    if errors:
        print("::error title=rh343::" + " | ".join(errors))
    else:
        print("::error title=rh343::OK plus-menu dedup + worked-time fallback")


main()