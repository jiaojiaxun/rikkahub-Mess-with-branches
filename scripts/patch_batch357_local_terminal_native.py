#!/usr/bin/env python3
# rhLocalTerminal357: P2 本地终端 · native 层
#
# 上游 rikkahub/rikkahub@master 的 :terminal 模块里，本地终端由 libtermux.so 提供 PTY：
#   terminal/src/main/cpp/CMakeLists.txt      -> project("terminal") / add_library(termux SHARED termux_pty.cpp)
#   terminal/src/main/cpp/termux_pty.cpp      -> JNI createSubprocess / setPtyWindowSize / waitFor / close
#   terminal/src/main/java/.../JNI.java       -> System.loadLibrary("termux")
#   terminal/src/main/java/.../LocalPtyTransport.java -> TerminalTransport 的本地实现
#
# fork 的 :terminal 只搬了 emulator 的 Java 部分（355a/355b，当时没有 cmake），
# 所以这里补 native 与 transport。上层接线（terminalLaunch / Manager 本地分支）在 358/359。
#
# 幂等：四个文件按 存在且足够大且含关键符号 判断；gradle 按 MARK 判断。

import os
import sys
import urllib.request

MARK = "rhLocalTerminal357"
BASE = "https://raw.githubusercontent.com/rikkahub/rikkahub/master/terminal/src/main"

REPO = os.getcwd()
TERM_DIR = os.path.abspath(os.path.join(REPO, "terminal"))
CPP_DIR = os.path.join(TERM_DIR, "src", "main", "cpp")
JAVA_DIR = os.path.join(TERM_DIR, "src", "main", "java", "com", "termux", "terminal")
GRADLE = os.path.join(TERM_DIR, "build.gradle.kts")
DIAG = os.path.join(REPO, "ci_diag_batch357_local_terminal.txt")

TARGETS = [
    ("/cpp/CMakeLists.txt", os.path.join(CPP_DIR, "CMakeLists.txt"), 150, "add_library(termux SHARED"),
    ("/cpp/termux_pty.cpp", os.path.join(CPP_DIR, "termux_pty.cpp"), 3000, "Java_com_termux_terminal_JNI_createSubprocess"),
    ("/java/com/termux/terminal/JNI.java", os.path.join(JAVA_DIR, "JNI.java"), 900, 'loadLibrary("termux")'),
    ("/java/com/termux/terminal/LocalPtyTransport.java", os.path.join(JAVA_DIR, "LocalPtyTransport.java"), 4000, "implements TerminalTransport"),
]

GRADLE_OLD = '    namespace = "me.rerere.terminal"\n}'
GRADLE_NEW = (
    '    namespace = "me.rerere.terminal"\n'
    '\n'
    '    defaultConfig {\n'
    '        ndk {\n'
    '            abiFilters += listOf("arm64-v8a")\n'
    '        }\n'
    '    }\n'
    '\n'
    '    externalNativeBuild {\n'
    '        cmake {\n'
    '            path = file("src/main/cpp/CMakeLists.txt")\n'
    '            version = "3.22.1"\n'
    '        }\n'
    '    }\n'
    '}\n'
    '\n'
    '// ' + MARK + ': libtermux.so powers the local workspace terminal\n'
)

OUT = []


def log(line):
    OUT.append(line)
    print(line)


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "rikkahub-ci"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read().decode("utf-8")


def write_text(path, text):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


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
        out.append(ch)
        i += 1
    return "".join(out)


def flush_diag():
    write_text(DIAG, "\n".join(OUT) + "\n")


def main():
    failures = []

    for suffix, path, min_size, needle in TARGETS:
        name = os.path.basename(path)
        if os.path.isfile(path) and os.path.getsize(path) >= min_size:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                existing = handle.read()
            if needle in existing:
                log("exists:" + name + ":" + str(len(existing)))
                continue
        try:
            text = fetch(BASE + suffix)
        except Exception as error:
            failures.append("fetch:" + name + ":" + str(error))
            log("fetch-fail:" + name + ":" + str(error))
            continue
        if len(text) < min_size:
            failures.append("short:" + name + ":" + str(len(text)))
            log("short:" + name + ":" + str(len(text)))
            continue
        if needle not in text:
            failures.append("needle:" + name)
            log("needle-missing:" + name)
            continue
        write_text(path, text)
        log("wrote:" + name + ":" + str(len(text)))

    if not os.path.isfile(GRADLE):
        failures.append("gradle-missing")
        log("gradle-missing")
    else:
        with open(GRADLE, "r", encoding="utf-8") as handle:
            gradle_text = handle.read()
        if MARK in gradle_text:
            log("gradle:already")
        elif gradle_text.count(GRADLE_OLD) != 1:
            failures.append("gradle-anchor:" + str(gradle_text.count(GRADLE_OLD)))
            log("gradle-anchor-count:" + str(gradle_text.count(GRADLE_OLD)))
        else:
            updated = gradle_text.replace(GRADLE_OLD, GRADLE_NEW)
            write_text(GRADLE, updated)
            log("gradle:rewritten")
        with open(GRADLE, "r", encoding="utf-8") as handle:
            gradle_text = handle.read()
        if "externalNativeBuild" not in gradle_text:
            failures.append("gradle-no-external-native")
        if "src/main/cpp/CMakeLists.txt" not in gradle_text:
            failures.append("gradle-no-cmake-path")
        stripped = strip_literals(gradle_text)
        diff = stripped.count("{") - stripped.count("}")
        log("gradle-braces:" + str(diff))
        if diff != 0:
            failures.append("gradle-braces:" + str(diff))

    for name in ("CMakeLists.txt", "termux_pty.cpp", "JNI.java", "LocalPtyTransport.java"):
        found = False
        for _suffix, path, _min_size, _needle in TARGETS:
            if os.path.basename(path) == name and os.path.isfile(path) and os.path.getsize(path) > 0:
                found = True
        if not found:
            failures.append("missing:" + name)
            log("missing:" + name)
        else:
            log("present:" + name)

    if failures:
        log("RESULT:FAIL")
        log("failures:" + "|".join(failures))
        flush_diag()
        sys.exit(1)

    log("RESULT:OK")
    flush_diag()


if __name__ == "__main__":
    main()
