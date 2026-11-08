#!/usr/bin/env python3
# rhRemote355h: 详情页双存储区切换（工作目录 / 根目录）—— 对齐官方 A9④
# 勘探结论: VM 已有 selectArea(area)（重置 path/entries 并 refresh）; State 已有 area;
# FilesPage 只有 14 个参数(含多选), 无 area 参数 → 加 2 参 + 切换行 + 组件 + 调用点传参。
import os

DIAG = "ci_diag_batch355h_remote.txt"
ROOT = os.environ.get("GITHUB_WORKSPACE", os.getcwd())


def read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def write(p, t):
    d = os.path.dirname(p)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(p, "w", encoding="utf-8") as f:
        f.write(t)


DIAG_LINES = []


def patch(path, edits):
    global DIAG_LINES
    text = read(path)
    for label, needle, repl in edits:
        if repl in text:
            DIAG_LINES.append(label + ":already")
            continue
        if text.count(needle) != 1:
            DIAG_LINES.append(label + ":ANCHOR-MISMATCH(" + str(text.count(needle)) + ")")
            continue
        text = text.replace(needle, repl, 1)
        DIAG_LINES.append(label + ":ok")
    write(path, text)


PAGE = "app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/WorkspaceDetailPage.kt"

# 1) import: Segmented 三件 + WorkspaceStorageArea
IMPORT_ANCHOR = "import androidx.compose.material3.Scaffold\n"
IMPORT_NEW = (
    "import androidx.compose.material3.Scaffold\n"
    "import androidx.compose.material3.SegmentedButton\n"
    "import androidx.compose.material3.SegmentedButtonDefaults\n"
    "import androidx.compose.material3.SingleChoiceSegmentedButtonRow\n"
)

AREA_IMPORT_ANCHOR = "import me.rerere.workspace.WorkspaceFileEntry\n"
AREA_IMPORT_NEW = (
    "import me.rerere.workspace.WorkspaceFileEntry\n"
    "import me.rerere.workspace.WorkspaceStorageArea\n"
)

# 2) FilesPage 签名加两参
SIG_ANCHOR = "private fun WorkspaceFilesPage(\n    state: WorkspaceDetailState,\n"
SIG_NEW = (
    "private fun WorkspaceFilesPage(\n"
    "    state: WorkspaceDetailState,\n"
    "    area: WorkspaceStorageArea,\n"
    "    onSelectArea: (WorkspaceStorageArea) -> Unit,\n"
)

# 3) path bar 之后插入切换行（锚点: state.error?.let 之前）
SELECTOR_ANCHOR = "        state.error?.let { error ->\n            item {\n                ErrorCard(error)\n            }\n        }\n"
SELECTOR_NEW = (
    "        item {\n"
    "            WorkspaceAreaSelector(area = area, onSelectArea = onSelectArea)\n"
    "        }\n\n" + SELECTOR_ANCHOR
)

# 4) 组件定义（插在 WorkspacePathBar 前）
PATHBAR_ANCHOR = "@Composable\nprivate fun WorkspacePathBar(\n"
PATHBAR_NEW = (
    "@Composable\n"
    "private fun WorkspaceAreaSelector(\n"
    "    area: WorkspaceStorageArea,\n"
    "    onSelectArea: (WorkspaceStorageArea) -> Unit,\n"
    ") {\n"
    "    val options = listOf(\n"
    "        WorkspaceStorageArea.FILES to stringResource(R.string.workspace_detail_area_files),\n"
    "        WorkspaceStorageArea.LINUX to stringResource(R.string.workspace_detail_area_linux),\n"
    "    )\n"
    "    SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {\n"
    "        options.forEachIndexed { index, (value, label) ->\n"
    "            SegmentedButton(\n"
    "                selected = area == value,\n"
    "                onClick = { onSelectArea(value) },\n"
    "                shape = SegmentedButtonDefaults.itemShape(index, options.size),\n"
    "            ) {\n"
    "                Text(label)\n"
    "            }\n"
    "        }\n"
    "    }\n"
    "}\n\n" + PATHBAR_ANCHOR
)

# 5) 调用点传参
CALL_ANCHOR = "                1 -> WorkspaceFilesPage(\n                    state = state,\n"
CALL_NEW = (
    "                1 -> WorkspaceFilesPage(\n"
    "                    state = state,\n"
    "                    area = state.area,\n"
    "                    onSelectArea = vm::selectArea,\n"
)

STRINGS_EN = '  <string name="workspace_detail_area_linux">Root directory</string>\n'
STRINGS_ZH = '  <string name="workspace_detail_area_linux">根目录</string>\n'


def main():
    ok = True
    patch(PAGE, [
        ("import-segmented", IMPORT_ANCHOR, IMPORT_NEW),
        ("import-area", AREA_IMPORT_ANCHOR, AREA_IMPORT_NEW),
        ("sig", SIG_ANCHOR, SIG_NEW),
        ("selector-row", SELECTOR_ANCHOR, SELECTOR_NEW),
        ("selector-fn", PATHBAR_ANCHOR, PATHBAR_NEW),
        ("call", CALL_ANCHOR, CALL_NEW),
    ])

    for path, block, label in (
        ("app/src/main/res/values/strings.xml", STRINGS_EN, "strings-en"),
        ("app/src/main/res/values-zh/strings.xml", STRINGS_ZH, "strings-zh"),
    ):
        text = read(path)
        if 'name="workspace_detail_area_linux"' in text:
            DIAG_LINES.append(label + ":already")
            continue
        anchor = "</resources>"
        if text.count(anchor) != 1:
            DIAG_LINES.append(label + ":ANCHOR-MISMATCH")
            ok = False
            continue
        text = text.replace(anchor, block + anchor, 1)
        write(path, text)
        DIAG_LINES.append(label + ":ok")

    final = read(PAGE)
    for needle in (
        "import androidx.compose.material3.SegmentedButton\n",
        "import androidx.compose.material3.SingleChoiceSegmentedButtonRow\n",
        "import me.rerere.workspace.WorkspaceStorageArea\n",
        "    area: WorkspaceStorageArea,\n    onSelectArea: (WorkspaceStorageArea) -> Unit,\n)",
        "WorkspaceAreaSelector(area = area, onSelectArea = onSelectArea)",
        "private fun WorkspaceAreaSelector(",
        "                    area = state.area,\n                    onSelectArea = vm::selectArea,\n",
    ):
        if needle not in final:
            DIAG_LINES.append("MISS:" + needle[:44].replace("\n", "|"))
            ok = False

    # 括号配平 + 组件内必须引用 area 两值
    if final.count("{") != final.count("}"):
        DIAG_LINES.append("BRACES(" + str(final.count("{")) + "/" + str(final.count("}")) + ")")
        ok = False
    seg = final[final.find("private fun WorkspaceAreaSelector("):]
    seg = seg[:seg.find("@Composable", 10)] if "@Composable" in seg[10:] else seg
    for needle in ("WorkspaceStorageArea.FILES", "WorkspaceStorageArea.LINUX", "onSelectArea(value)"):
        if needle not in seg:
            DIAG_LINES.append("SEL-MISS:" + needle)
            ok = False

    DIAG_LINES.append("RESULT:" + ("OK" if ok else "FAIL"))
    with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
        f.write("\n".join(DIAG_LINES) + "\n")
    print(" | ".join(DIAG_LINES))
    if not ok:
        print("::error title=batch355h::" + " | ".join(DIAG_LINES))


main()
