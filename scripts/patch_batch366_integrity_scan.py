#!/usr/bin/env python3
# rhIntegrity366: 只读全量排查 —— 编译期查不出、运行期才炸的两类集成点
#
# 起因：WorkspaceSshEditorVM 漏注册 Koin 导致打开页面直接崩，而 CI 六项验收全绿。
# 这说明「编译过 / 测试过 / 打包过」并不能证明依赖能解析。本批把所有同类隐患一次扫干净。
#
# 检查 A —— Koin 定义完整性
#   收集 app 模块里所有显式类型参数的解析点：
#       koinViewModel<X>() / koinInject<X>()
#   收集 4 个 DI 文件里所有注册点：
#       viewModelOf(::X) / viewModel<X> / single<X> / factory<X>
#       single { X(...) } / viewModel { X(...) }（含全限定名，取最后一段）
#   差集 = 被解析但没注册的类 → 运行到那一行就 NoDefinitionFoundException
#   误报控制：只报告仓库里确实存在 class 定义的名字（接口/框架类型不报）
#
# 检查 B —— 路由完整性
#   收集 RouteActivity.kt 里所有 `data class Xxx(...) : Screen` 定义
#   收集所有 `entry<Screen.Xxx>` 注册
#   差集 = 定义了 Screen 但没有 entry → navigate 过去必定崩溃
#
# 本批不改任何代码，只写 ci_diag_batch366_integrity.txt，永不 exit(1)。

import os
import re

REPO = os.getcwd()
APP = os.path.join(REPO, "app", "src", "main", "java")
DI_DIR = os.path.join(APP, "me", "rerere", "rikkahub", "di")
ROUTE = os.path.join(APP, "me", "rerere", "rikkahub", "RouteActivity.kt")
DIAG = os.path.join(REPO, "ci_diag_batch366_integrity.txt")

DI_FILES = [
    os.path.join(DI_DIR, "ViewModelModule.kt"),
    os.path.join(DI_DIR, "AppModule.kt"),
    os.path.join(DI_DIR, "RepositoryModule.kt"),
    os.path.join(DI_DIR, "DataSourceModule.kt"),
]

USE_PATTERN = re.compile(r"\b(?:koinViewModel|koinInject)\s*<\s*([A-Za-z_][\w.]*)\s*>")
REG_PATTERNS = [
    re.compile(r"viewModelOf\s*\(\s*::\s*(\w+)"),
    re.compile(r"viewModel\s*<\s*([A-Za-z_][\w.]*)\s*>"),
    re.compile(r"single\s*<\s*([A-Za-z_][\w.]*)\s*>"),
    re.compile(r"factory\s*<\s*([A-Za-z_][\w.]*)\s*>"),
    re.compile(r"viewModel\s*\{\s*([\w.]+)\s*\("),
    re.compile(r"single\s*\{\s*([\w.]+)\s*\("),
]
CLASS_PATTERN = re.compile(
    r"^\s*(?:internal |private |public |abstract |open |sealed |data |enum |annotation )*class\s+(\w+)",
    re.MULTILINE,
)
SCREEN_PATTERN = re.compile(r"data class (\w+)\s*\([^)]*\)\s*:\s*Screen", re.DOTALL)
ENTRY_PATTERN = re.compile(r"entry<\s*Screen\.(\w+)\s*>")

OUT = []


def log(line):
    OUT.append(line)
    print(line)


def short(name):
    return name.rsplit(".", 1)[-1]


def walk_kotlin(root):
    for folder, _dirs, files in os.walk(root):
        for name in files:
            if name.endswith(".kt"):
                yield os.path.join(folder, name)


def read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def main():
    # --- 收集仓库中真实存在的 class 名 ---
    classes = set()
    uses = {}
    for path in walk_kotlin(APP):
        text = read(path)
        for match in CLASS_PATTERN.finditer(text):
            classes.add(match.group(1))
        for match in USE_PATTERN.finditer(text):
            name = short(match.group(1))
            uses.setdefault(name, []).append(os.path.relpath(path, REPO))

    log("classes:" + str(len(classes)))
    log("koin-use-sites:" + str(len(uses)))

    # --- 收集已注册的类型名 ---
    registered = set()
    di_text = ""
    for path in DI_FILES:
        if not os.path.isfile(path):
            log("missing-di:" + os.path.basename(path))
            continue
        text = read(path)
        di_text += text + "\n"
        for pattern in REG_PATTERNS:
            for match in pattern.finditer(text):
                registered.add(short(match.group(1)))

    log("registered:" + str(len(registered)))

    # --- 检查 A：差集 ---
    missing = []
    for name in sorted(uses):
        if name in registered:
            continue
        if name not in classes:
            # 框架类型或接口，静态判断容易误报，不计入
            continue
        missing.append(name)
        log("MISSING-KOIN:" + name + " @ " + ",".join(sorted(set(uses[name]))[:3]))

    if not missing:
        log("koin:all-resolved")

    # --- 检查 B：路由完整性 ---
    if os.path.isfile(ROUTE):
        route_text = read(ROUTE)
        screens = sorted(set(SCREEN_PATTERN.findall(route_text)))
        entries = sorted(set(ENTRY_PATTERN.findall(route_text)))
        log("screens:" + str(len(screens)) + " entries:" + str(len(entries)))
        no_entry = [name for name in screens if name not in entries]
        for name in no_entry:
            log("MISSING-ENTRY:" + name)
        if not no_entry:
            log("route:all-defined-screens-have-entry")
        orphan_entry = [name for name in entries if name not in screens]
        for name in orphan_entry:
            log("ORPHAN-ENTRY:" + name)
    else:
        log("missing-route-activity")

    # --- 汇总 ---
    if missing:
        log("RESULT:FAIL koin-missing=" + str(len(missing)))
    else:
        log("RESULT:OK")

    with open(DIAG, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()
