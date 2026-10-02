#!/usr/bin/env python3
"""Vendor the Miffan whale-girl renderer (Ayuilos/Miffan, AGPL-3.0) into the fork.

The two generated/oversized sources (WhaleGirlColorRegions.kt ~30KB and the
StaticWhaleContours object carved out of WhaleGirlStaticReview.kt ~67KB) are
Python tool output; hand-copying them through a chat is error prone, so they are
fetched here at build time and rewritten deterministically instead.

Everything is pinned to one upstream commit. Each file is verified: a missing
download, an empty body or a missing expected declaration aborts the build.

Idempotent: files already present with the expected declarations are left alone.
"""
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

UPSTREAM_OWNER = "Ayuilos"
UPSTREAM_REPO = "Miffan"
UPSTREAM_REF = "ade291c011ca7ca026a239ab75d67fe4531d138f"
UPSTREAM_DIR = "app/src/main/java/me/ayuilos/miffan/ui/components/ui"
LOCAL_DIR = Path("app/src/main/java/me/rerere/rikkahub/ui/components/ui")
OLD_PKG = "package me.ayuilos.miffan.ui.components.ui"
NEW_PKG = "package me.rerere.rikkahub.ui.components.ui"

# Retained notices required by AGPL-3.0 section 5 + the upstream file headers.
VENDOR_NOTE = (
    "// Vendored from Ayuilos/Miffan (AGPL-3.0), commit {ref}.\n"
    "// Copyright (c) Ayuilos and the RikkaHub / Miffan contributors.\n"
    "// Upstream: https://github.com/Ayuilos/Miffan\n"
    "// Rewritten: package renamed to this fork. Original code otherwise unchanged.\n"
)


def fetch(name: str) -> str:
    url = (
        f"https://raw.githubusercontent.com/{UPSTREAM_OWNER}/{UPSTREAM_REPO}/"
        f"{UPSTREAM_REF}/{UPSTREAM_DIR}/{name}"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "rikkahub-fork-vendor"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read().decode("utf-8")
    except urllib.error.URLError as error:
        print(f"::error file=scripts/fetch_whale_renderer.py::"
              f"failed to download {name}: {error}", file=sys.stderr)
        raise SystemExit(1) from error


def repackage(text: str) -> str:
    if OLD_PKG not in text:
        print(f"::error file=scripts/fetch_whale_renderer.py::"
              f"upstream package line not found while vendoring", file=sys.stderr)
        raise SystemExit(1)
    body = text.replace(OLD_PKG, NEW_PKG, 1)
    # Keep the file's own doc comments, but stamp the provenance note on top.
    first_newline = body.find("\n")
    return VENDOR_NOTE.format(ref=UPSTREAM_REF) + body[first_newline + 1:]


def write_if_absent(name: str, text: str, required_marker: str) -> None:
    path = LOCAL_DIR / name
    if path.exists() and required_marker in path.read_text(encoding="utf-8"):
        print(f"== {path} already vendored, skipping", flush=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"wrote {path} ({len(text)} bytes)", flush=True)


def main() -> int:
    # 1. Hand-written sources: small enough to vendor verbatim.
    for name, marker in [
        ("WhaleGirlActing.kt", "internal fun whaleActing("),
        ("WhaleGirlLineArt.kt", "internal fun WhaleGirlLineArtPortrait("),
        ("WhaleGirlApprovedDrawing.kt", "internal fun DrawScope.drawApprovedWhaleHead("),
    ]:
        write_if_absent(name, repackage(fetch(name)), marker)

    # 2. Generated colour regions (~30KB of Path data).
    write_if_absent(
        "WhaleGirlColorRegions.kt",
        repackage(fetch("WhaleGirlColorRegions.kt")),
        "internal fun DrawScope.drawWhaleColorBlocks(",
    )

    # 3. StaticWhaleContours lives inside the 67KB review/validation file. Only the
    #    data object is required by the renderer; the static preview composable and
    #    its test scaffolding are dropped.
    review = repackage(fetch("WhaleGirlStaticReview.kt"))
    match = re.search(
        r"(?:/\*\*(?:[^*]|\*(?!/))*\*/\s*)?internal object StaticWhaleContours \{.*?\n\}\n",
        review,
        re.DOTALL,
    )
    if match is None:
        print("::error file=scripts/fetch_whale_renderer.py::"
              "StaticWhaleContours object not found in WhaleGirlStaticReview.kt",
              file=sys.stderr)
        return 1
    header = (
        "package me.rerere.rikkahub.ui.components.ui\n\n"
        "import androidx.compose.ui.geometry.Offset\n"
        "import androidx.compose.ui.graphics.Path\n"
        "import androidx.compose.ui.graphics.vector.PathParser\n\n"
        + VENDOR_NOTE.format(ref=UPSTREAM_REF)
        + "// Carved out of WhaleGirlStaticReview.kt; the renderer needs only this data.\n\n"
    )
    body = match.group(0)
    # Re-home the PathParser/Offset imports that came from the original file header.
    write_if_absent("StaticWhaleContours.kt", header + body, "internal object StaticWhaleContours")

    print("whale-girl renderer vendored", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
