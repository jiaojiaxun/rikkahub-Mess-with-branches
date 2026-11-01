"""batch325 — composer placeholder matches the reference wording.

dsh-go's field reads 「给 DSH 发消息…」; our string resource is a generic hint.
Render the assistant name in the same shape, falling back to the resource when
the name is blank. Single-line anchor inside TextInputRow, where `assistant` is
already resolved from LocalSettings.
"""

import os

ROOT = os.getcwd()
CHAT_INPUT = os.path.join(
    ROOT,
    "app/src/main/java/me/rerere/rikkahub/ui/components/ai/ChatInput.kt",
)
DIAG = os.path.join(ROOT, "ci_diag_batch325_placeholder.txt")

log = []


def note(m):
    print(m)
    log.append(str(m))


def bal(t):
    return (t.count('{') - t.count('}'), t.count('(') - t.count(')'))


def main():
    src = open(CHAT_INPUT, "r", encoding="utf-8").read()
    before = bal(src)

    old = "            placeholder = {\n                Text(stringResource(R.string.chat_input_placeholder))\n            },"
    new = (
        "            placeholder = { // rhDsh325\n"
        "                Text(\n"
        "                    text = if (assistant.name.isBlank()) {\n"
        "                        stringResource(R.string.chat_input_placeholder)\n"
        "                    } else {\n"
        "                        \"给 \" + assistant.name + \" 发消息…\"\n"
        "                    }\n"
        "                )\n"
        "            },"
    )

    count = src.count(old)
    note("placeholder: anchor count=" + str(count) + " backup_count=" + str(src.count("R.string.chat_input_placeholder")))

    if count != 1:
        print("::error title=rhDsh325::anchor count=" + str(count))
        open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
        return

    src = src.replace(old, new)
    after = bal(src)
    if after != before:
        raise SystemExit("balance " + str(before) + " -> " + str(after))
    if "发消息…" not in src:
        raise SystemExit("replacement missing")
    open(CHAT_INPUT, "w", encoding="utf-8").write(src)
    note("placeholder: assistant-name wording installed")
    print("::error title=rhDsh325::OK placeholder now 给 <assistant> 发消息…")
    open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")


main()