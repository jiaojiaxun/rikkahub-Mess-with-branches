#!/usr/bin/env python3
"""Batch-9: make the WebDAV download progress actually visible.

Reported as "WebDAV 备份的时候下载要有进度条".

The plumbing already exists end to end:
  WebDavClient.downloadToFile -> per-chunk (completed, total)
  WebDavSync.restore          -> BackupProgress("下载备份", ...)
  BackupVM.runWithProgress    -> vm.progress
  WebDavTab                   -> progress?.let { WebDavProgressCard(it) }

The bug is placement. Restore is started from the backup-file ModalBottomSheet, and
showBackupFiles was only set to false AFTER vm.restore() returned. The sheet therefore
stayed on top for the whole download and hid WebDavProgressCard, which lives in the main
scrollable column behind it - the user only saw the row's small spinner.

Fix:
  * close the sheet before the restore starts, and scroll the main column back to the top
    so the progress card is on screen while the download runs
  * drop the "0%" prefix when the server reports no size (PROPFIND without
    getcontentlength and a chunked GET), so the card reads as "已下载 3.2 MiB" instead of
    a bogus "0%"

Anchored, idempotent, loud (::error + exit 1).
"""
import sys
from pathlib import Path

FAILURES = []
TARGET = Path("app/src/main/java/me/rerere/rikkahub/ui/pages/backup/tabs/WebDavTab.kt")
MARKER = "rh-batch9"


def fail(msg):
    print(f"::error file={TARGET}::batch9 patch failed: {msg}", flush=True)
    FAILURES.append(msg)


def flatten(text):
    kept = []
    indexes = []
    for index, char in enumerate(text):
        if not char.isspace():
            kept.append(char)
            indexes.append(index)
    return "".join(kept), indexes


def match_flat(src, pattern):
    flat_src, indexes = flatten(src)
    flat_pattern, _ = flatten(pattern)
    if not flat_pattern:
        return None
    positions = flat_src.count(flat_pattern)
    if positions != 1:
        return ("count", positions)
    start_flat = flat_src.find(flat_pattern)
    end_flat = start_flat + len(flat_pattern) - 1
    return (indexes[start_flat], indexes[end_flat] + 1)


def replace_once(src, pattern, replacement, label):
    found = match_flat(src, pattern)
    if found is None:
        fail(f"{label}: empty anchor")
        return None
    if isinstance(found[0], str):
        fail(f"{label}: expected 1 match, found {found[1]}")
        return None
    start, end = found
    return src[:start] + replacement + src[end:]


SCROLL_STATE_OLD = """    val scope = rememberCoroutineScope()
    var showBackupFiles by remember { mutableStateOf(false) }"""

SCROLL_STATE_NEW = """    val scope = rememberCoroutineScope()
    // rh-batch9: the download progress card sits at the top of this scrollable column, so the
    // restore flow needs a handle on the scroll position to bring it back on screen.
    val scrollState = rememberScrollState()
    var showBackupFiles by remember { mutableStateOf(false) }"""

SCROLL_USE_OLD = """            modifier = Modifier
                .weight(1f)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),"""

SCROLL_USE_NEW = """            modifier = Modifier
                .weight(1f)
                .verticalScroll(scrollState)
                .padding(16.dp),"""

MERGE_OLD = """                        if (item != null) scope.launch {
                            restoringItemId = item.displayName
                            runCatching {
                                vm.restore(item, BackupRestoreMode.MERGE)"""

MERGE_NEW = """                        if (item != null) scope.launch {
                            restoringItemId = item.displayName
                            // rh-batch9: close the sheet FIRST. It used to stay open for the whole
                            // restore and hide the WebDavProgressCard carrying the download
                            // progress. Scrolling back to the top puts that card on screen.
                            showBackupFiles = false
                            scrollState.scrollTo(0)
                            runCatching {
                                vm.restore(item, BackupRestoreMode.MERGE)"""

OVERWRITE_OLD = """                        if (item != null) scope.launch {
                            restoringItemId = item.displayName
                            runCatching {
                                vm.restore(item, BackupRestoreMode.OVERWRITE)"""

OVERWRITE_NEW = """                        if (item != null) scope.launch {
                            restoringItemId = item.displayName
                            // rh-batch9: see the MERGE branch - reveal the progress card.
                            showBackupFiles = false
                            scrollState.scrollTo(0)
                            runCatching {
                                vm.restore(item, BackupRestoreMode.OVERWRITE)"""

PERCENT_OLD = 'Text("${progress.percent ?: 0}% · ${progress.detail}")'

PERCENT_NEW = """Text(
                        // rh-batch9: a server that omits the size (no getcontentlength on
                        // PROPFIND and a chunked GET) has nothing to be a percentage of, so
                        // show the byte detail on its own instead of a misleading "0%".
                        progress.percent?.let { "$it% · ${progress.detail}" } ?: progress.detail
                    )"""


def main():
    if not TARGET.exists():
        fail("file not found")
        print("batch9 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
        return 1
    src = TARGET.read_text(encoding="utf-8")
    if MARKER in src:
        print("already patched: " + str(TARGET), flush=True)
        return 0
    original = src

    for old, new, label in (
        (SCROLL_STATE_OLD, SCROLL_STATE_NEW, "scroll state"),
        (SCROLL_USE_OLD, SCROLL_USE_NEW, "scrollable column"),
        (MERGE_OLD, MERGE_NEW, "MERGE restore"),
        (OVERWRITE_OLD, OVERWRITE_NEW, "OVERWRITE restore"),
        (PERCENT_OLD, PERCENT_NEW, "progress percentage"),
    ):
        src = replace_once(src, old, new, label)
        if src is None:
            print("batch9 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
            return 1

    if src == original or MARKER not in src:
        fail("nothing changed")
        print("batch9 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
        return 1

    TARGET.write_text(src, encoding="utf-8")
    print("patched: " + str(TARGET), flush=True)
    print("batch9 patches applied", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
