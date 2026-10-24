#!/usr/bin/env python3
# batch283: 引用/预览链路不再泄露隐藏段（心率）。
#
# 缺陷：引用带 rikkahub.hidden 心率段的消息时——
#   1. ChatService 的引用注入（batch95）把被引消息全部 Text part 拼进上下文 → 心率重复注入；
#   2. ChatList 引用块预览用 quotedMsg.toText() → toText() 不过滤 → 心率段直接显示在引用小卡上；
#   3. toText()/summaryAsText() 是所有预览/标题/摘要的公共出口，同样不过滤。
# 修法：隐藏段概念下沉到 ai 模块（UIMessagePart.isHidden + HIDDEN_PART_META_KEY 常量单源），
#   toText()/summaryAsText() 统一 filterNot；ChatService 引用注入加一道过滤；注入器改用同一常量。
# MARK=rhHiddenPart283
import sys
from pathlib import Path

MARK = "rhHiddenPart283"
NL = chr(10)
DIAG = "ci_diag_batch283.txt"
applied = []
failed = []

UIPART = "ai/src/main/java/me/rerere/ai/ui/UIMessagePart.kt"
MESSAGE = "ai/src/main/java/me/rerere/ai/ui/Message.kt"
CS = "app/src/main/java/me/rerere/rikkahub/service/ChatService.kt"
INJ = "app/src/main/java/me/rerere/rikkahub/data/ble/HeartRateShareInjector.kt"


def diag(msg):
    try:
        with open(DIAG, "a", encoding="utf-8") as f:
            f.write(msg + NL)
    except Exception:
        pass


def fail(msg):
    diag("FAIL " + msg)
    print("::error title=batch283::" + msg)
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
        fail(label + " anchor count=" + str(len(hits)))
    lines.insert(hits[0] + 1, block)
    applied.append(label)
    return NL.join(lines)


def edit_uipart():
    content = read(UIPART)
    if MARK in content:
        diag("uipart already patched")
        return
    old = (
        "fun ToolApprovalState.canResumeToolExecution(): Boolean {" + NL
        + "    return when (this) {" + NL
        + "        ToolApprovalState.Approved -> true" + NL
        + "        is ToolApprovalState.Denied -> true" + NL
        + "        is ToolApprovalState.Answered -> true" + NL
        + "        ToolApprovalState.Auto," + NL
        + "        ToolApprovalState.Pending," + NL
        + "            -> false" + NL
        + "    }" + NL
        + "}"
    )
    new = (
        old + NL + NL
        + "/**" + NL
        + " * " + MARK + ": 隐藏段单源定义。metadata 里带 rikkahub.hidden=true 的 Text part" + NL
        + " * 是只给模型看的注入内容（如心率），一切面向用户的文本出口（toText/summaryAsText/引用预览）" + NL
        + " * 都应当把它过滤掉。app 模块的心率注入器写 metadata 时也用这个键。" + NL
        + " */" + NL
        + "const val HIDDEN_PART_META_KEY = \"rikkahub.hidden\"" + NL
        + "" + NL
        + "val UIMessagePart.isHidden: Boolean" + NL
        + "    get() = (metadata?.get(HIDDEN_PART_META_KEY) as? kotlinx.serialization.json.JsonPrimitive)?.content == \"true\""
    )
    content = replace_text(content, old, new, "uipart-extension")
    write(UIPART, content)


def edit_message():
    content = read(MESSAGE)
    if MARK in content:
        diag("message already patched")
        return
    old_totext = "    fun toText() = parts.joinToString(separator = \"\\n\") { part ->"
    new_totext = "    fun toText() = parts.filterNot { it.isHidden }.joinToString(separator = \"\\n\") { part -> // " + MARK
    content = replace_text(content, old_totext, new_totext, "message-totext")

    old_summary = "        val text = \"[${role.name}]: \" + parts.joinToString(separator = \"\\n\") { part ->"
    new_summary = "        val text = \"[${role.name}]: \" + parts.filterNot { it.isHidden }.joinToString(separator = \"\\n\") { part -> // " + MARK
    content = replace_text(content, old_summary, new_summary, "message-summary")
    write(MESSAGE, content)


def edit_chatservice():
    content = read(CS)
    if MARK in content:
        diag("chatservice already patched")
        return
    old = (
        "        ?.parts" + NL
        + "        ?.filterIsInstance<UIMessagePart.Text>()" + NL
        + "        ?.joinToString(\"\\n\") { it.text }"
    )
    new = (
        "        ?.parts" + NL
        + "        ?.filterIsInstance<UIMessagePart.Text>()" + NL
        + "        ?.filterNot { it.isHidden } // " + MARK + ": 引用注入不带隐藏段（心率）" + NL
        + "        ?.joinToString(\"\\n\") { it.text }"
    )
    content = replace_text(content, old, new, "chatservice-quote-filter")

    if "import me.rerere.ai.ui.isHidden" not in content:
        content = insert_after_line(
            content,
            "import me.rerere.ai.ui.UIMessagePart",
            "import me.rerere.ai.ui.isHidden // " + MARK,
            "chatservice-import",
        )
    write(CS, content)


def edit_injector():
    content = read(INJ)
    if MARK in content:
        diag("injector already patched")
        return
    old = "    const val HIDDEN_META_KEY = \"rikkahub.hidden\""
    new = "    const val HIDDEN_META_KEY = me.rerere.ai.ui.HIDDEN_PART_META_KEY // " + MARK + ": 键与 ai 模块同源"
    content = replace_text(content, old, new, "injector-const")
    write(INJ, content)


def main():
    for label, fn in (
        ("uipart", edit_uipart),
        ("message", edit_message),
        ("chatservice", edit_chatservice),
        ("injector", edit_injector),
    ):
        try:
            fn()
        except SystemExit:
            failed.append(label)
        except Exception as e:
            diag("EXCEPTION " + label + ": " + repr(e))
            failed.append(label)

    # 读回断言：四个文件的关键符号都在
    checks = [
        (UIPART, "val UIMessagePart.isHidden: Boolean"),
        (UIPART, "const val HIDDEN_PART_META_KEY"),
        (MESSAGE, "parts.filterNot { it.isHidden }"),
        (CS, "?.filterNot { it.isHidden }"),
        (INJ, "me.rerere.ai.ui.HIDDEN_PART_META_KEY"),
    ]
    if not failed:
        for path, needle in checks:
            if needle not in read(path):
                fail("verify failed: " + path + " missing " + needle)

    diag("applied=" + ",".join(applied) + " failed=" + (",".join(failed) if failed else "none"))
    if failed:
        print("::error title=batch283-FAILED::" + ",".join(failed))
    else:
        print("::notice title=batch283-ok::" + ",".join(applied))


main()
