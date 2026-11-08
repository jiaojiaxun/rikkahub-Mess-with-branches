#!/usr/bin/env python3
# rhIntegrity366 (v2): 修误报 + 新增「同文件改写链」统计
#
# v1 的两个误报（已核实）：
#   1) MISSING-KOIN: PluginLoader / PluginRepository @ PluginWebViewPage.kt
#      —— 它们注册在 plugin/di/PluginModule.kt，v1 的 DI_FILES 只列了 4 个文件，漏了这个。
#   2) 一堆 ORPHAN-ENTRY
#      —— SCREEN_PATTERN 只写了 `data class`，而实际一半 Screen 是 `data object`，
#         于是那些 object 全被判成"有 entry 没定义"。
#
# v2 三件事：
#   A) DI_FILES 补 plugin/di/PluginModule.kt
#   B) SCREEN_PATTERN 改成 `data (?:class|object)`，并允许无参数（object 没有括号）
#   C) 新增「同文件改写链」统计：扫 scripts/patch_batch*.py 里出现的 .kt 文件名，
#      统计每个文件被多少个批次脚本引用 —— 用来提前发现「后一批依赖前一批产物」的脆弱链
#      （371→372 就是这类：371 插入、372 再改 371 的产物）。
#
# 只读，永不 exit(1)。输出 ci_diag_batch366_integrity.txt。

import os
import re

REPO = os.getcwd()
APP = os.path.join(REPO, "app", "src", "main", "java")
DI_DIR = os.path.join(APP, "me", "rerere", "rikkahub", "di")
ROUTE = os.path.join(APP, "me", "rerere", "rikkahub", "RouteActivity.kt")
SCRIPTS_DIR = os.path.join(REPO, "scripts")
DIAG = os.path.join(REPO, "ci_diag_batch366_integrity.txt")

DI_FILES = [
    os.path.join(DI_DIR, "ViewModelModule.kt"),
    os.path.join(DI_DIR, "AppModule.kt"),
    os.path.join(DI_DIR, "RepositoryModule.kt"),
    os.path.join(DI_DIR, "DataSourceModule.kt"),
    os.path.join(APP, "me", "rerere", "rikkahub", "plugin", "di", "PluginModule.kt"),
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
SCREEN_PATTERN = re.compile(
    r"data\s+(?:class|object)\s+(\w+)(?:\s*\([^)]*\))?\s*:\s*Screen",
    re.DOTALL,
)
ENTRY_PATTERN = re.compile(r"entry<\s*Screen\.(\w+)\s*>")
KT_LITERAL = re.compile(r"[\w./-]+\.kt")
MAX_CHAINS = 40

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


def scan_chains():
    chain = {}
    if not os.path.isdir(SCRIPTS_DIR):
        return chain
    for name in sorted(os.listdir(SCRIPTS_DIR)):
        if not (name.startswith("patch_batch") and name.endswith(".py")):
            continue
        path = os.path.join(SCRIPTS_DIR, name)
        try:
            content = read(path)
        except OSError:
            continue
        for match in KT_LITERAL.findall(content):
            base = os.path.basename(match)
            chain.setdefault(base, set()).add(name)
    return chain


def main():
    # A/B 基础数据
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

    log("di-files-present:" + str(sum(1 for path in DI_FILES if os.path.isfile(path))))
    log("registered:" + str(len(registered)))

    missing = []
    for name in sorted(uses):
        if name in registered:
            continue
        if name not in classes:
            continue
        missing.append(name)
        log("MISSING-KOIN:" + name + " @ " + ",".join(sorted(set(uses[name]))[:3]))
    log("koin-missing:" + str(len(missing)))

    # 路由
    if os.path.isfile(ROUTE):
        route_text = read(ROUTE)
        screens = sorted(set(SCREEN_PATTERN.findall(route_text)))
        entries = sorted(set(ENTRY_PATTERN.findall(route_text)))
        log("screens:" + str(len(screens)) + " entries:" + str(len(entries)))
        no_entry = [name for name in screens if name not in entries]
        for name in no_entry:
            log("MISSING-ENTRY:" + name)
        orphan = [name for name in entries if name not in screens]
        for name in orphan:
            log("ORPHAN-ENTRY:" + name)
        log("missing-entry:" + str(len(no_entry)) + " orphan-entry:" + str(len(orphan)))
    else:
        log("missing-route-activity")

    # C) 同文件改写链
    chain = scan_chains()
    multi = [(base, scripts) for base, scripts in chain.items() if len(scripts) >= 2]
    multi.sort(key=lambda item: (-len(item[1]), item[0]))
    log("")
    log("=== chain: files touched by >=2 batch scripts: " + str(len(multi)) + " ===")
    for base, scripts in multi[:MAX_CHAINS]:
        ordered = sorted(scripts)
        log("chain:" + base + " x" + str(len(ordered)) + " :: " + ",".join(ordered))
    if len(multi) > MAX_CHAINS:
        log("chain-truncated:" + str(len(multi) - MAX_CHAINS))

    log("")
    log("RESULT:OK")
    with open(DIAG, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()
