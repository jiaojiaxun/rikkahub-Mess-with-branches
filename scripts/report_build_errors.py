#!/usr/bin/env python3
"""Surface Gradle/Kotlin build failures as GitHub check-run annotations.

CI logs cannot be downloaded without auth on this setup, but check-run annotations are
world-readable, so this script converts the interesting parts of a Gradle log into
`::error` workflow commands:

  * Kotlin compiler errors (`e: file:line:col message`) -> file/line anchored annotations
  * failing Gradle tasks, the "What went wrong" block, "Execution failed for task" lines
  * the `Caused by:` chain, plus a raw window around the first FAILURE line

Usage: python3 scripts/report_build_errors.py [logfile]
Always exits 0 -- reporting must never mask the real build result.
"""
import re
import sys
from pathlib import Path

KOTLIN_ERR = re.compile(r"^e: (?:file://)?(\S+?):(\d+):(\d+)[:\s]*(.*)$", re.MULTILINE)
TASK_FAILED = re.compile(r"^> Task (\S+) FAILED$", re.MULTILINE)
CAUSE = re.compile(r"^Caused by: (.*)$", re.MULTILINE)
WHAT_WENT_WRONG = re.compile(
    r"\* What went wrong:\s*\n(.*?)(?:\n\* Try:|\n\* Get more help|\Z)", re.DOTALL
)
EXEC_FAILED = re.compile(r"^Execution failed for task '([^']+)'\.?\s*(.*)$", re.MULTILINE)
MAX_KOTLIN = 25


def sanitize(text: str, limit: int = 900) -> str:
    cleaned = (
        text.replace("%", "%25")
        .replace("\r", " ")
        .replace("\n", " | ")
        .replace("::", ": ")
    )
    return cleaned.strip()[:limit]


def emit(message: str) -> None:
    print(f"::error::{sanitize(message)}")


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "build.log")
    if not path.exists():
        emit("log file missing: the step failed before Gradle produced output")
        return 0

    log = path.read_text(encoding="utf-8", errors="replace")

    # 1) Kotlin compiler errors -- the only ones with useful file/line anchors.
    kotlin_count = 0
    for file_path, line, col, message in KOTLIN_ERR.findall(log):
        if kotlin_count >= MAX_KOTLIN:
            break
        rel = file_path.split("/repo/", 1)[1] if "/repo/" in file_path else file_path
        print(f"::error file={rel},line={line},col={col}::{sanitize(message, 380)}")
        kotlin_count += 1

    # 2) Which tasks blew up.
    failed_tasks = TASK_FAILED.findall(log)
    if failed_tasks:
        emit("FAILED tasks: " + ", ".join(failed_tasks[:12]))

    # 3) The canonical "What went wrong" block.
    match = WHAT_WENT_WRONG.search(log)
    if match:
        emit("WHAT WENT WRONG: " + match.group(1)[:1200])

    # 4) Explicit task failures with their reason.
    for task, extra in EXEC_FAILED.findall(log)[:4]:
        emit(f"EXEC FAILED: {task} :: {extra}")

    # 5) Root-cause chain.
    for cause in CAUSE.findall(log)[:6]:
        emit("CAUSED BY: " + cause[:600])

    # 6) Raw context around the first FAILURE banner, in case all else misses.
    idx = log.find("FAILURE: Build failed")
    if idx >= 0:
        emit("AROUND FAILURE: " + log[idx : idx + 1400])

    print(f"reported {kotlin_count} kotlin error annotation(s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
