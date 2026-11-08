#!/usr/bin/env python3
# rhDiFix365: P0 —— WorkspaceSshEditorVM 没注册到 Koin，打开远程工作区编辑页直接崩
#
# 崩溃现场（用户实测）：
#   org.koin.core.error.NoDefinitionFoundException:
#     No definition found for type '...WorkspaceSshEditorVM' on scope '['_root_']'
#     at ...WorkspacePageKt.WorkspaceSshEditorPage(...)
#
# 根因（实读确认）：
#   WorkspaceSshEditorPage.kt:
#       val vm: WorkspaceSshEditorVM = koinViewModel(key = "ssh-editor-$id", parameters = { parametersOf(id) })
#   WorkspaceSshEditorVM.kt:
#       class WorkspaceSshEditorVM(private val id: String?, private val repository: WorkspaceRepository)
#   而 ViewModelModule.kt 里只注册了 WorkspaceVM / WorkspaceInstallVM / WorkspaceDetailVM，
#   唯独漏了 WorkspaceSshEditorVM —— 352a 移植这个页面时只建了类，没写 DI。
#
# 为什么 CI 全绿也抓不到：Koin 是运行时解析，编译期不校验；页面不打开就不会触发。
#
# 本批做两件事：
#   1) 注册 WorkspaceSshEditorVM（params 取 id，与 Page 的 parametersOf(id) 对应）
#   2) 只读全量排查：扫 workspace 包下所有 *VM 类，逐个检查 DI 文件里有没有出现，
#      把 MISSING 的写进诊断 —— 避免"修一个崩一个"

import os
import re
import sys

MARK = "rhDiFix365"
REPO = os.getcwd()
APP = os.path.join(REPO, "app", "src", "main", "java", "me", "rerere", "rikkahub")
VM_MODULE = os.path.join(APP, "di", "ViewModelModule.kt")
WS_DIR = os.path.join(APP, "ui", "pages", "extensions", "workspace")
DI_FILES = [
    os.path.join(APP, "di", "ViewModelModule.kt"),
    os.path.join(APP, "di", "AppModule.kt"),
    os.path.join(APP, "di", "RepositoryModule.kt"),
    os.path.join(APP, "di", "DataSourceModule.kt"),
]
DIAG = os.path.join(REPO, "ci_diag_batch365_koin_vm.txt")

IMPORT_OLD = (
    'import me.rerere.rikkahub.ui.pages.extensions.workspace.WorkspaceInstallVM\n'
    'import me.rerere.rikkahub.ui.pages.extensions.workspace.WorkspaceVM\n'
)
IMPORT_NEW = (
    'import me.rerere.rikkahub.ui.pages.extensions.workspace.WorkspaceInstallVM\n'
    'import me.rerere.rikkahub.ui.pages.extensions.workspace.WorkspaceSshEditorVM\n'
    'import me.rerere.rikkahub.ui.pages.extensions.workspace.WorkspaceVM\n'
)

BLOCK_OLD = (
    '    viewModel<WorkspaceDetailVM> {\n'
    '        WorkspaceDetailVM(\n'
    '            id = it.get(),\n'
    '            repository = get(),\n'
    '        )\n'
    '    }\n'
)
BLOCK_NEW = (
    '    viewModel<WorkspaceDetailVM> {\n'
    '        WorkspaceDetailVM(\n'
    '            id = it.get(),\n'
    '            repository = get(),\n'
    '        )\n'
    '    }\n'
    '\n'
    '    // ' + MARK + ': SSH 工作区编辑页。params 是工作区 id（新建时为 null），\n'
    '    // 与 WorkspaceSshEditorPage 里 koinViewModel(parameters = { parametersOf(id) }) 一一对应。\n'
    '    viewModel<WorkspaceSshEditorVM> { params ->\n'
    '        WorkspaceSshEditorVM(\n'
    '            id = params.get(),\n'
    '            repository = get(),\n'
    '        )\n'
    '    }\n'
)

OUT = []


def log(line):
    OUT.append(line)
    print(line)


def strip_literals(source):
    out = []
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        if ch == '"' or ch == "'":
            quote = ch
            i += 1
            while i < n:
                if source[i] == "\\":
                    i += 2
                    continue
                if source[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            while i < n and source[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "*":
            i += 2
            while i + 1 < n and not (source[i] == "*" and source[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def counts(text):
    stripped = strip_literals(text)
    return stripped.count("{") - stripped.count("}"), stripped.count("(") - stripped.count(")")


def main():
    failures = []

    if not os.path.isfile(VM_MODULE):
        log("missing-file:viewmodelmodule")
        with open(DIAG, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("missing-file:viewmodelmodule\nRESULT:FAIL\n")
        sys.exit(1)

    with open(VM_MODULE, "r", encoding="utf-8") as handle:
        text = handle.read()
    before = counts(text)

    # 1) import
    if "workspace.WorkspaceSshEditorVM" in text:
        log("already:import")
    else:
        hits = text.count(IMPORT_OLD)
        log("anchor-import:" + str(hits))
        if hits != 1:
            failures.append("anchor-import:" + str(hits))
        else:
            text = text.replace(IMPORT_OLD, IMPORT_NEW)
            log("wrote:import")

    # 2) viewModel 注册
    if "viewModel<WorkspaceSshEditorVM>" in text:
        log("already:registration")
    else:
        hits = text.count(BLOCK_OLD)
        log("anchor-block:" + str(hits))
        if hits != 1:
            failures.append("anchor-block:" + str(hits))
        else:
            text = text.replace(BLOCK_OLD, BLOCK_NEW)
            log("wrote:registration")

    after = counts(text)
    log("braces:" + str(before) + "->" + str(after))
    if before != after:
        failures.append("braces")

    with open(VM_MODULE, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    log("file-size:" + str(len(text)))

    # 3) 只读全量排查：workspace 包下每个 *VM 是否出现在任一 DI 文件里
    di_text = ""
    for path in DI_FILES:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as handle:
                di_text += handle.read() + "\n"

    pattern = re.compile(r"^(?:internal |private )?class (\w+)\s*[\(:]", re.MULTILINE)
    seen = []
    if os.path.isdir(WS_DIR):
        for name in sorted(os.listdir(WS_DIR)):
            if not name.endswith(".kt"):
                continue
            with open(os.path.join(WS_DIR, name), "r", encoding="utf-8", errors="replace") as handle:
                source = handle.read()
            for cls in pattern.findall(source):
                if not cls.endswith("VM"):
                    continue
                if cls in seen:
                    continue
                seen.append(cls)
                ok = cls in di_text
                log("vm:" + cls + ":" + ("ok" if ok else "MISSING"))
                if not ok:
                    failures.append("vm-missing:" + cls)
    else:
        log("missing-dir:workspace")
        failures.append("missing-dir:workspace")

    log("vm-total:" + str(len(seen)))

    # 4) 复核注册本身
    with open(VM_MODULE, "r", encoding="utf-8") as handle:
        final = handle.read()
    checks = [
        ("import-present", "workspace.WorkspaceSshEditorVM" in final),
        ("registration-present", "viewModel<WorkspaceSshEditorVM>" in final),
        ("params-id", "id = params.get()," in final),
        ("detail-still-there", "viewModel<WorkspaceDetailVM>" in final),
        ("mark-present", MARK in final),
    ]
    for name, ok in checks:
        log("check:" + name + ":" + ("ok" if ok else "FAIL"))
        if not ok:
            failures.append("check:" + name)

    if failures:
        log("RESULT:FAIL")
        log("failures:" + "|".join(failures))
    else:
        log("RESULT:OK")

    with open(DIAG, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(OUT) + "\n")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
