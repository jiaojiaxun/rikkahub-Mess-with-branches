#!/usr/bin/env python3
"""Batch-6 v2: replace PURE_OFFICIAL with LITE (lite backup, no uploads).

v1 added PURE_OFFICIAL (OfficialPurifier净化). User wants three modes simplified
to two + a new lite mode. v2 renames PURE_OFFICIAL -> LITE and changes behavior:
LITE skips uploads/ attachments instead of purifying the DB.

Files touched (same as v1):
1. WebDavSync.kt: LITE skips uploads dir (not OfficialPurifier).
2. ImportExportTab.kt: third export row for LITE.
3. Strings: rename pure -> lite.
"""
import glob
import re
import sys
from pathlib import Path

FAILURES = []
WEBDAV = "app/src/main/java/me/rerere/rikkahub/data/sync/webdav/WebDavSync.kt"
TAB = "app/src/main/java/me/rerere/rikkahub/ui/pages/backup/tabs/ImportExportTab.kt"


def fail(path, msg):
    print(f"::error file={path}::batch6v2 patch failed: {msg}", flush=True)
    FAILURES.append(f"{path}: {msg}")


def patch(path, marker, transform):
    p = Path(path)
    if not p.exists():
        fail(path, "file not found")
        return
    src = p.read_text(encoding="utf-8")
    if marker in src:
        print(f"already patched ({marker}): {path}", flush=True)
        return
    out = transform(src)
    if not out or out == src or marker not in out:
        fail(path, f"anchor not found for {marker}")
        return
    p.write_text(out, encoding="utf-8")
    print(f"patched ({marker}): {path}", flush=True)


def sub_once(pattern, replacement, src):
    pat = re.compile(pattern)
    if len(pat.findall(src)) != 1:
        return None
    return pat.sub(lambda _m: replacement, src, count=1)


# LITE: skip uploads dir (include uploads only when format == FULL)
SETTINGS_NEW = """val officialSettings = createOfficialSettingsText().let { text ->
            // rh-batch6v2:lite-settings (lite = same settings, no uploads in archive)
            text
        }.toByteArray()"""

DB_NEW = """// rh-batch6v2:lite-db (lite = full agent DB snapshot, but no uploads/ in archive)
                if (full || format == BackupExportFormat.LITE) agentDb = createFullDatabaseSnapshot(dbRoot)"""


def t_settings(src):
    return sub_once(r"val officialSettings = createOfficialSettingsText\(\)\.toByteArray\(\)", SETTINGS_NEW, src)


def t_db(src):
    return sub_once(r"if \(full\) agentDb = createFullDatabaseSnapshot\(dbRoot\)", DB_NEW, src)


LITE_ITEM = """item(
                    onClick = if (!isExporting && !isRestoring) {
                        {
                            selectedExportFormat = BackupExportFormat.LITE
                            createDocumentLauncher.launch("rikkahub_lite_backup.zip")
                        }
                    } else null,
                    headlineContent = { Text("\u8f7b\u91cf\u5907\u4efd\uff08\u4e0d\u542b\u9644\u4ef6\uff09") },
                    supportingContent = {
                        Text(
                            if (isExporting && selectedExportFormat == BackupExportFormat.LITE) {
                                "\u6b63\u5728\u5bfc\u51fa\uff1a${progress?.detail.orEmpty()}"
                            } else "\u53ea\u5907\u4efd\u5bf9\u8bdd\u6570\u636e\u548c\u8bbe\u7f6e\uff0c\u4e0d\u542b uploads/ \u9644\u4ef6\uff0c\u4f53\u79ef\u5c0f"
                        )
                    },
                    leadingContent = {
                        if (isExporting && selectedExportFormat == BackupExportFormat.LITE) {
                            CircularWavyProgressIndicator(modifier = Modifier.size(24.dp))
                        } else Icon(HugeIcons.File01, null)
                    },
                )
                """


def t_tab(src):
    pat = re.compile(
        r"item\(\s*onClick = if \(!isExporting && !isRestoring\) \{\s*\{\s*"
        r"selectedExportFormat = BackupExportFormat\.FULL"
    )
    ms = list(pat.finditer(src))
    if len(ms) != 1:
        return None
    return src[: ms[0].start()] + LITE_ITEM + src[ms[0].start():]


RENAME = {
    "en": {
        "backup_page_local_backup_export_official": "Compatible export (lenient)",
        "backup_page_local_backup_export_official_desc": "The previous official-compatible export: RikkaHub 2.4.14 can restore it; fork-only fields are kept and ignored by the official app",
    },
    "zh": {
        "backup_page_local_backup_export_official": "\u517c\u5bb9\u5bfc\u51fa\uff08\u5bff\u677e\uff09",
        "backup_page_local_backup_export_official_desc": "\u6cba\u7528\u539f\u300c\u5b98\u65b9\u517c\u5bb9\u300d\u903b\u8f91\uff1aRikkaHub 2.4.14 \u53ef\u4ee5\u6062\u590d\uff0c\u4e8c\u6539\u591a\u51fa\u7684\u5b57\u6bb5\u539f\u6837\u5e26\u4e0a\uff0c\u7531\u5b98\u65b9\u7248\u81ea\u884c\u5ffd\u7565",
    },
}
ADD = {
    "en": {
        "backup_page_local_backup_export_pure": "Lite backup (no attachments)",
        "backup_page_local_backup_export_pure_desc": "Backs up conversation data and settings only, without uploads/ attachments. Much smaller than a full backup",
    },
    "zh": {
        "backup_page_local_backup_export_pure": "\u8f7b\u91cf\u5907\u4efd\uff08\u4e0d\u542b\u9644\u4ef6\uff09",
        "backup_page_local_backup_export_pure_desc": "\u53ea\u5907\u4efd\u5bf9\u8bdd\u6570\u636e\u548c\u8bbe\u7f6e\uff0c\u4e0d\u542b uploads/ \u9644\u4ef6\uff0c\u4f53\u79ef\u5c0f",
    },
}


def patch_strings_file(path, lang, required):
    p = Path(path)
    src = p.read_text(encoding="utf-8")
    out = src
    for key, value in RENAME[lang].items():
        pat = re.compile(r'(<string name="' + re.escape(key) + r'"[^>]*>)(.*?)(</string>)', re.S)
        if not pat.search(out):
            if required:
                fail(path, f"string {key} not found")
            continue
        out = pat.sub(lambda m, v=value: m.group(1) + v + m.group(3), out, count=1)
    missing = {k: v for k, v in ADD[lang].items() if f'name="{k}"' not in out}
    if missing:
        end = out.rfind("</resources>")
        if end < 0:
            fail(path, "no </resources>")
            return
        lines = "".join(f'    <string name="{k}">{v}</string>\n' for k, v in missing.items())
        out = out[:end] + lines + out[end:]
    if out != src:
        p.write_text(out, encoding="utf-8")
        print(f"strings updated: {path}", flush=True)


def patch_strings():
    base = "app/src/main/res"
    default = f"{base}/values/strings.xml"
    if not Path(default).exists():
        fail(default, "file not found")
        return
    patch_strings_file(default, "en", required=True)
    for path in glob.glob(f"{base}/values-zh*/strings.xml"):
        patch_strings_file(path, "zh", required=False)


def main():
    patch(WEBDAV, "rh-batch6v2:lite-settings", t_settings)
    patch(WEBDAV, "rh-batch6v2:lite-db", t_db)
    patch(TAB, "BackupExportFormat.LITE", t_tab)
    patch_strings()
    if FAILURES:
        print("batch6v2 patch failures:\n  " + "\n  " + "\n  ".join(FAILURES), flush=True)
        return 1
    print("batch6v2 patches applied", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
