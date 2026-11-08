#!/usr/bin/env python3
# rhRemote355m: 文件编辑器分区只读 + 详情页 Shell 状态徽章
# 1) 编辑器既有 bug: 读取用 readTextForPreview(area) 支持 LINUX, 但保存用 writeText(无 area)
#    固定写 FILES → 在 LINUX 区编辑保存会把内容落到 FILES 同名路径(数据错位)。
#    官方 A9④: FILES 可编辑, LINUX 只读。修法: readOnly/保存按钮按 area 门控 + 标题加(只读)。
# 2) 详情页基本信息卡补 Shell 状态行(READY/INSTALLING/BROKEN/DISABLED)。
# 同文件冲突核对: DetailPage 锚点取"area_files 两行", 与 353/355f/355h/355j 插入点不重叠。
import os

DIAG = "ci_diag_batch355m_workspace.txt"
ROOT = os.environ.get("GITHUB_WORKSPACE", os.getcwd())


def read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def write(p, t):
    with open(p, "w", encoding="utf-8") as f:
        f.write(t)


diag = []
ok = True


def patch_file(path, edits):
    global ok
    text = read(path)
    for label, needle, repl in edits:
        if repl in text:
            diag.append(label + ":already")
            continue
        if text.count(needle) != 1:
            diag.append(label + ":ANCHOR-MISMATCH(" + str(text.count(needle)) + ")")
            ok = False
            continue
        text = text.replace(needle, repl, 1)
        diag.append(label + ":ok")
    write(path, text)
    return text


EDITOR = "app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/WorkspaceFileEditorPage.kt"
DETAIL = "app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/WorkspaceDetailPage.kt"

# --- 1) 编辑器 ---
editor_text = patch_file(EDITOR, [
    (
        "editor-readonly",
        "                readOnly = false,\n",
        "                readOnly = area != WorkspaceStorageArea.FILES,\n",
    ),
    (
        "editor-save-gate",
        "                    if (!loading && loadError == null) {\n",
        "                    if (!loading && loadError == null && area == WorkspaceStorageArea.FILES) {\n",
    ),
    (
        "editor-title",
        "                    Text(\n"
        "                        text = fileName,\n",
        "                    Text(\n"
        "                        text = if (area == WorkspaceStorageArea.FILES) {\n"
        "                            fileName\n"
        "                        } else {\n"
        "                            fileName + \" (\" + stringResource(R.string.workspace_file_read_only) + \")\"\n"
        "                        },\n",
    ),
])

for needle in (
    "                readOnly = area != WorkspaceStorageArea.FILES,",
    "loadError == null && area == WorkspaceStorageArea.FILES",
    "R.string.workspace_file_read_only",
):
    if needle not in editor_text:
        diag.append("EDITOR-MISS:" + needle[:40])
        ok = False

# --- 2) 详情页 Shell 状态 ---
detail_text = patch_file(DETAIL, [
    (
        "detail-shell",
        "                    WorkspaceInfoRow(\n"
        "                        stringResource(R.string.workspace_detail_area_files),\n"
        "                        stringResource(R.string.workspace_detail_area_files),\n"
        "                    )\n",
        "                    WorkspaceInfoRow(\n"
        "                        stringResource(R.string.workspace_detail_area_files),\n"
        "                        stringResource(R.string.workspace_detail_area_files),\n"
        "                    )\n"
        "                    WorkspaceInfoRow(\n"
        "                        stringResource(R.string.workspace_detail_shell_status),\n"
        "                        when (workspace?.shellStatus) {\n"
        "                            \"READY\" -> stringResource(R.string.workspace_detail_shell_ready)\n"
        "                            \"INSTALLING\" -> stringResource(R.string.workspace_detail_shell_installing)\n"
        "                            \"BROKEN\" -> stringResource(R.string.workspace_detail_shell_broken)\n"
        "                            else -> stringResource(R.string.workspace_detail_shell_disabled)\n"
        "                        },\n"
        "                    )\n",
    ),
])

for needle in (
    "R.string.workspace_detail_shell_status",
    "R.string.workspace_detail_shell_ready",
    "R.string.workspace_detail_shell_installing",
    "R.string.workspace_detail_shell_broken",
    "R.string.workspace_detail_shell_disabled",
):
    if needle not in detail_text:
        diag.append("DETAIL-MISS:" + needle)
        ok = False

# --- 3) strings ---
STRINGS_EN = r'''  <string name="workspace_detail_shell_status">Shell</string>
  <string name="workspace_detail_shell_ready">Ready</string>
  <string name="workspace_detail_shell_installing">Installing…</string>
  <string name="workspace_detail_shell_broken">Broken</string>
  <string name="workspace_detail_shell_disabled">Disabled</string>
  <string name="workspace_file_read_only">read-only</string>
'''
STRINGS_ZH = r'''  <string name="workspace_detail_shell_status">Shell</string>
  <string name="workspace_detail_shell_ready">已就绪</string>
  <string name="workspace_detail_shell_installing">安装中…</string>
  <string name="workspace_detail_shell_broken">损坏</string>
  <string name="workspace_detail_shell_disabled">未启用</string>
  <string name="workspace_file_read_only">只读</string>
'''

for path, block, label in (
    ("app/src/main/res/values/strings.xml", STRINGS_EN, "strings-en"),
    ("app/src/main/res/values-zh/strings.xml", STRINGS_ZH, "strings-zh"),
):
    text = read(path)
    if 'name="workspace_detail_shell_status"' in text:
        diag.append(label + ":already")
        continue
    anchor = "</resources>"
    if text.count(anchor) != 1:
        diag.append(label + ":ANCHOR-MISMATCH")
        ok = False
        continue
    write(path, text.replace(anchor, block + anchor, 1))
    diag.append(label + ":ok")

# --- 4) 自检: 括号配平 ---
for path, label in ((EDITOR, "editor"), (DETAIL, "detail")):
    t = read(path)
    if t.count("{") != t.count("}"):
        diag.append(label + ":BRACES(" + str(t.count("{")) + "/" + str(t.count("}")) + ")")
        ok = False
    if t.count("(") != t.count(")"):
        diag.append(label + ":PARENS(" + str(t.count("(")) + "/" + str(t.count(")")) + ")")
        ok = False

diag.append("RESULT:" + ("OK" if ok else "FAIL"))
with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
    f.write("\n".join(diag) + "\n")
print(" | ".join(diag))
if not ok:
    print("::error title=batch355m::" + " | ".join(diag))
