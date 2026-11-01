"""batch320 — static-review fixes for the dsh chrome batch.

Found by adversarial self-review before compiling:
1) RhDshStat used Modifier.weight outside a RowScope receiver -> compile error.
2) The old composer's "more" (files / compression / injection) entry was deleted
   with the capability row and never re-hosted -> dead feature.
   Add onMoreClick to RhDshPlusKey and pass it from ChatInput.
Runs after 318/319 (sort -V: 318_ < 319_ < 320_).
"""

import os

ROOT = os.getcwd()
APP = os.path.join(ROOT, "app/src/main/java/me/rerere/rikkahub")
CHROME = os.path.join(APP, "ui/components/ai/RhDshChrome.kt")
CHAT_INPUT = os.path.join(APP, "ui/components/ai/ChatInput.kt")
DIAG = os.path.join(ROOT, "ci_diag_batch320_dsh_fix.txt")

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


def balance(t):
    return t.count('{') - t.count('}'), t.count('(') - t.count(')')


def fix_chrome():
    src = read(CHROME)
    before = balance(src)

    imp_anchor = "import androidx.compose.foundation.layout.Row\n"
    if src.count(imp_anchor) != 1:
        raise ValueError("Row import anchor count=" + str(src.count(imp_anchor)))
    src = src.replace(
        imp_anchor,
        imp_anchor + "import androidx.compose.foundation.layout.RowScope\n",
    )

    stat_anchor = "@Composable\nprivate fun RhDshStat(label: String, value: String) {"
    if src.count(stat_anchor) != 1:
        raise ValueError("RhDshStat anchor count=" + str(src.count(stat_anchor)))
    src = src.replace(
        stat_anchor,
        "@Composable\nprivate fun RowScope.RhDshStat(label: String, value: String) {",
    )

    sig_anchor = "    onPickFile: () -> Unit,\n    capabilities: @Composable () -> Unit,\n) {"
    if src.count(sig_anchor) != 1:
        raise ValueError("RhDshPlusKey signature anchor count=" + str(src.count(sig_anchor)))
    src = src.replace(
        sig_anchor,
        "    onPickFile: () -> Unit,\n    onMoreClick: () -> Unit = {},\n    capabilities: @Composable () -> Unit,\n) {",
    )

    menu_anchor = (
        "            Row(\n"
        "                modifier = Modifier\n"
        "                    .fillMaxWidth()\n"
        "                    .padding(horizontal = 8.dp, vertical = 4.dp),"
    )
    if src.count(menu_anchor) != 1:
        raise ValueError("plus menu anchor count=" + str(src.count(menu_anchor)))
    more_item = (
        "            DropdownMenuItem(\n"
        "                text = { Text(\"文件与工具\") },\n"
        "                leadingIcon = { Icon(HugeIcons.Files02, contentDescription = null) },\n"
        "                onClick = {\n"
        "                    expanded = false\n"
        "                    onMoreClick()\n"
        "                },\n"
        "            )\n"
    )
    src = src.replace(menu_anchor, more_item + menu_anchor)

    after = balance(src)
    if after != before:
        raise ValueError("chrome balance drift " + str(before) + " -> " + str(after))
    for must in ["RowScope.RhDshStat", "onMoreClick: () -> Unit", "文件与工具"]:
        if must not in src:
            raise ValueError("chrome missing " + must)
    write(CHROME, src)
    log("chrome: fixed (" + str(len(src)) + " bytes)")


def fix_chat_input():
    src = read(CHAT_INPUT)
    before = balance(src)
    anchor = "                            onPickFile = onPickFile,\n                        ) {"
    if src.count(anchor) != 1:
        raise ValueError("plus call anchor count=" + str(src.count(anchor)))
    src = src.replace(
        anchor,
        "                            onPickFile = onPickFile,\n"
        "                            onMoreClick = onMoreClick, // rhDshFix320\n"
        "                        ) {",
    )
    after = balance(src)
    if after != before:
        raise ValueError("chatinput balance drift " + str(before) + " -> " + str(after))
    if "onMoreClick = onMoreClick" not in src:
        raise ValueError("chatinput missing more wiring")
    write(CHAT_INPUT, src)
    log("chatinput: more wired (" + str(len(src)) + " bytes)")


def main():
    errors = []
    for name, fn in (("chrome", fix_chrome), ("chatinput", fix_chat_input)):
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
        print("::error title=rhDsh320::" + " | ".join(errors))
    else:
        print("::error title=rhDsh320::OK RowScope stat + more entry re-hosted")


main()