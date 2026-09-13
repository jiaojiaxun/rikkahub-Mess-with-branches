#!/usr/bin/env python3
"""Surface Kotlin/Gradle build errors as GitHub check-run annotations (baseline).

CI logs need auth to download; check-run annotations are world-readable on a public
repo. Emitting `::error file=...,line=...::message` workflow commands turns compiler
errors into annotations.

Usage: python3 scripts/baseline_report_errors.py [build.log]
Always exits 0.
"""
import re
import sys
from pathlib import Path

ERR_RE = re.compile(r"^e: (?:file://)?(\S+?):(\d+):(\d+)[:\s]*(.*)$", re.MULTILINE)
MAX_ANNOTATIONS = 40
MAX_MSG = 380


def relativise(path: str) -> str:
    marker = "/repo/"
    if marker in path:
        return path.split(marker, 1)[1]
    return path


def sanitize(text: str) -> str:
    return (
        text.replace("%", "%25")
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("::", ": ")
        .strip()
    )


def main() -> int:
    log_path = Path(sys.argv[1] if len(sys.argv) > 1 else "build.log")
    if not log_path.exists():
        print("::error::build.log missing; build failed before producing output")
        return 0

    log = log_path.read_text(encoding="utf-8", errors="replace")
    hits = ERR_RE.findall(log)

    emitted = 0
    for path, line, col, msg in hits:
        if emitted >= MAX_ANNOTATIONS:
            break
        clean = sanitize(msg)[:MAX_MSG]
        if not clean:
            continue
        print(f"::error file={relativise(path)},line={line},col={col}::{clean}")
        emitted += 1

    if emitted == 0:
        noisy = [
            line.strip()
            for line in log.splitlines()
            if line.strip() and not line.strip().startswith("Download")
        ][-15:]
        summary = sanitize(" | ".join(noisy))[:900]
        print(f"::error::no Kotlin errors parsed; tail: {summary}")

    print(f"reported {emitted} annotation(s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
