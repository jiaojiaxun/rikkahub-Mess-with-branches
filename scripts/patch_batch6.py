#!/usr/bin/env python3
"""Batch-6 build-time patches: "pure official" backup export.

Same convention as the other batches: anchored, idempotent, loud (::error + exit 1).
1. WebDavSync.prepareBackupFile: PURE_OFFICIAL purifies settings and the converted DB.
2. ImportExportTab: third export row for PURE_OFFICIAL.
3. Strings: the old official-compatible row is relabelled (logic unchanged), new strings
   for the pure row.
"""
import glob
import re
import sys
from pathlib import Path

FAILURES = []
WEBDAV = "app/src/main/java/me/rerere/rikkahub/data/sync/webdav/WebDavSync.kt"
TAB = "app/src/main/java/me/rerere/rikkahub/ui/pages/backup/tabs/ImportExportTab.kt"


def fail(path, msg):
    print(f"::error file={path}::batch6 patch failed: {msg}", flush=True)
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
    return pat.sub(lambda _m: replacement, src)


SETTINGS_NEW = """val officialSettings = createOfficialSettingsText().let { text ->
            // rh-batch6:pure-settings
            if (format == BackupExportFormat.PURE_OFFICIAL) OfficialPurifier.purifySettings(text) else text
        }.toByteArray()"""

DB_NEW = """// rh-batch6:pure-db
                if (format == BackupExportFormat.PURE_OFFICIAL) officialDb?.let { OfficialPurifier.purifyDatabase(it) }
                if (full) agentDb = createFullDatabaseSnapshot(dbRoot)"""


def t_settings(src):
    return sub_once(r"val officialSettings = createOfficialSettingsText\(\)\.toByteArray\(\)", SETTINGS_NEW, src)


def t_db(src):
    return sub_once(r"if \(full\) agentDb = createFullDatabaseSnapshot\(dbRoot\)", DB_NEW, src)


PURE_ITEM = """item(
                    onClick = if (!isExporting && !isRestoring) {
                        {
                            selectedExportFormat = BackupExportFormat.PURE_OFFICIAL
                            createDocumentLauncher.launch("rikkahub_pure_official_backup.zip")
                        }
                    } else null,
                    headlineContent = { Text(stringResource(R.string.backup_page_local_backup_export_pure)) },
                    supportingContent = {
                        Text(
                            if (isExporting && selectedExportFormat == BackupExportFormat.PURE_OFFICIAL) {
                                "正在导出：${progress?.detail.orEmpty()}"
                            } else stringResource(R.string.backup_page_local_backup_export_pure_desc)
                        )
                    },
                    leadingContent = {
                        if (isExporting && selectedExportFormat == BackupExportFormat.PURE_OFFICIAL) {
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
    return src[: ms[0].start()] + PURE_ITEM + src[ms[0].start():]


RENAME = {
    "en": {
        "backup_page_local_backup_export_official": "Compatible export (lenient)",
        "backup_page_local_backup_export_official_desc": "The previous official-compatible export: RikkaHub 2.4.14 can restore it; fork-only fields are kept and ignored by the official app",
    },
    "zh": {
        "backup_page_local_backup_export_official": "兼容导出（宽松）",
        "backup_page_local_backup_export_official_desc": "沿用原「官方兼容」逻辑：RikkaHub 2.4.14 可以恢复，二改多出的字段原样带上，由官方版自行忽略",
    },
}
ADD = {
    "en": {
        "backup_page_local_backup_export_pure": "Pure official export",
        "backup_page_local_backup_export_pure_desc": "Keeps only the tables, fields, providers and tools RikkaHub 2.4.14 knows; everything fork-only is removed. Best for moving back to the official app",
    },
    "zh": {
        "backup_page_local_backup_export_pure": "纯净官方导出",
        "backup_page_local_backup_export_pure_desc": "只保留 RikkaHub 2.4.14 认识的表、字段、供应商和工具，二改独有的内容全部删除，适合迁回官方版",
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
    patch(WEBDAV, "rh-batch6:pure-settings", t_settings)
    patch(WEBDAV, "rh-batch6:pure-db", t_db)
    patch(TAB, "BackupExportFormat.PURE_OFFICIAL", t_tab)
    patch_strings()
    if FAILURES:
        print("batch6 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
        return 1
    print("batch6 patches applied", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
