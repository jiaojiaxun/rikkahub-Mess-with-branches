"""batch324 — two correctness/polish fixes found while re-reading the wiring.

1) The context ring resolved its window from `currentChatModel`, which is
   Settings.getCurrentChatModel() = assistant.chatModelId ?: settings.chatModelId.
   That chain does NOT include the conversation-level model, so with
   "按对话固定模型" enabled the ring/sheet would measure against the assistant's
   model instead of the conversation's. Resolve it the same way the top-bar chip
   and the ChatInput provider lookup do:
       setting.getChatModelOf(conversation)?.modelId ?: currentChatModel?.modelId

2) ChatHtmlLayer.TOP_BAR_DP still carried the old top-bar height (64). The new
   header is 56, so skins kept an 8dp gap. Change is optional-guarded: if the
   constant does not look like 64, skip and report instead of guessing.

No new imports; every change is a single-line replacement with a balance check.
"""

import os

ROOT = os.getcwd()
APP = os.path.join(ROOT, "app/src/main/java/me/rerere/rikkahub")
CHAT_PAGE = os.path.join(APP, "ui/pages/chat/ChatPage.kt")
HTML_LAYER = os.path.join(APP, "ui/pages/chat/ChatHtmlLayer.kt")
DIAG = os.path.join(ROOT, "ci_diag_batch324_wiring_fix.txt")

log = []


def note(m):
    print(m)
    log.append(str(m))


def bal(t):
    return (t.count('{') - t.count('}'), t.count('(') - t.count(')'))


def fix_model_identifier():
    src = open(CHAT_PAGE, "r", encoding="utf-8").read()
    before = bal(src)

    old = "                        modelIdentifier = currentChatModel?.modelId,"
    new = "                        modelIdentifier = setting.getChatModelOf(conversation)?.modelId ?: currentChatModel?.modelId, // rhDsh324"
    count = src.count(old)
    note("chatpage: modelIdentifier anchor count=" + str(count))
    if count != 1:
        raise ValueError("anchor count=" + str(count))

    src = src.replace(old, new)
    after = bal(src)
    if after != before:
        raise ValueError("balance " + str(before) + " -> " + str(after))
    if "getChatModelOf(conversation)?.modelId ?: currentChatModel?.modelId" not in src:
        raise ValueError("replacement missing")
    open(CHAT_PAGE, "w", encoding="utf-8").write(src)
    note("chatpage: context window now resolves the conversation model first")


def fix_top_bar_dp():
    if not os.path.exists(HTML_LAYER):
        note("html layer: file missing, skip")
        return
    src = open(HTML_LAYER, "r", encoding="utf-8").read()
    before = bal(src)
    marker = "const val TOP_BAR_DP = 64"
    count = src.count(marker)
    note("html layer: TOP_BAR_DP=64 anchor count=" + str(count))
    if count != 1:
        note("html layer: constant not found as 64, leave unchanged")
        return
    src = src.replace(marker, "const val TOP_BAR_DP = 56 // rhDsh324")
    after = bal(src)
    if after != before:
        raise ValueError("html layer balance drift")
    open(HTML_LAYER, "w", encoding="utf-8").write(src)
    note("html layer: TOP_BAR_DP 64 -> 56")


def main():
    errors = []
    for name, fn in (("model_identifier", fix_model_identifier), ("top_bar_dp", fix_top_bar_dp)):
        try:
            fn()
        except Exception as exc:
            errors.append(name + " FAILED: " + str(exc))
            note(name + " FAILED: " + str(exc))

    open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
    if errors:
        print("::error title=rhDsh324::" + " | ".join(errors))
    else:
        print("::error title=rhDsh324::OK conversation model + html top bar height")


main()