#!/usr/bin/env python3
"""Batch-4 build-time patches (same convention as batch 1-3: anchored, idempotent, loud).

BackupArchiveRestorer:
1. FULL archives carry the fork's own database + settings under rikkahub_agent/ next to the
   official-compatible core. Restore those in place of the core when present.
2. Leaf-name aliases (settings.json, database.db, ...) only apply outside the file roots: a
   workspace or upload file that happens to be called settings.json or database.db must not
   replace the app settings or the database.
"""
import re
import sys
from pathlib import Path

FAILURES = []
RESTORER = "app/src/main/java/me/rerere/rikkahub/data/sync/webdav/BackupArchiveRestorer.kt"


def fail(path, msg):
    print(f"::error file={path}::batch4 patch failed: {msg}", flush=True)
    FAILURES.append(f"{path}: {msg}")


STAGE_DECLS = r"""
        // rh-batch4:agent-full
        val stagedAgentDb = File(staging, "agent_rikka_hub.db")
        var agentSettings: Settings? = null"""

AGENT_ENTRIES = r"""// FULL-format extras (see BackupExportFormat). They take precedence over the
                    // official-compatible core stored at the root of the same archive.
                    when (entry.name.replace('\\', '/').trim('/')) {
                        me.rerere.rikkahub.data.sync.AGENT_FULL_DB_ENTRY -> {
                            FileOutputStream(stagedAgentDb).use { output ->
                                consumeEntry(input, MAX_ENTRY_BYTES, "准备数据库", entry.name) { bytes, count ->
                                    output.write(bytes, 0, count)
                                }
                            }
                            input.closeEntry()
                            continue
                        }
                        me.rerere.rikkahub.data.sync.AGENT_FULL_SETTINGS_ENTRY -> {
                            val rawAgentSettings = ByteArrayOutputStream()
                            consumeEntry(input, MAX_SETTINGS_BYTES, "读取设置", entry.name) { bytes, count ->
                                rawAgentSettings.write(bytes, 0, count)
                            }
                            agentSettings = json.decodeFromString(
                                SettingsJsonMigrator.migrate(rawAgentSettings.toByteArray().toString(Charsets.UTF_8))
                            )
                            input.closeEntry()
                            continue
                        }
                    }
                    """

AFTER_EXTRACT = r"""
            if (stagedAgentDb.isFile) {
                // The FULL snapshot is a standalone database in this build's schema: it replaces
                // the converted core copy, and the core's empty sidecars must not be applied.
                moveReplacing(stagedAgentDb, stagedDb)
                stagedWal.delete()
                stagedShm.delete()
            }
            agentSettings?.let { importedSettings = it }"""

ROOT_GUARD = (
    'if (parts.none { it.lowercase() in setOf("upload", "uploads", "files", "skills", "skill", '
    '"fonts", "images", "tool_outputs", "tool-outputs", "workspaces", "workspace") }) '
    'when (parts.lastOrNull()?.lowercase()) {'
)


def t_restorer(src):
    m = re.search(r'val stagedShm = File\(staging, "rikka_hub-shm"\)', src)
    if not m or src.count('val stagedShm = File(staging, "rikka_hub-shm")') != 1:
        return None
    src = src[:m.end()] + STAGE_DECLS + src[m.end():]

    m = re.search(r"val safeName = normalizeEntryName\(entry\.name\)", src)
    if not m or src.count("val safeName = normalizeEntryName(entry.name)") != 1:
        return None
    src = src[:m.start()] + AGENT_ENTRIES + src[m.start():]

    m = re.search(r'report\(\s*"校验备份",\s*"安全解压完成"\s*\)', src)
    if not m:
        return None
    src = src[:m.end()] + AFTER_EXTRACT + src[m.end():]

    anchor = "when (parts.lastOrNull()?.lowercase()) {"
    if src.count(anchor) != 1:
        return None
    return src.replace(anchor, ROOT_GUARD, 1)


def main():
    p = Path(RESTORER)
    if not p.exists():
        fail(RESTORER, "file not found")
    else:
        src = p.read_text(encoding="utf-8")
        if "rh-batch4:agent-full" in src:
            print(f"already patched: {RESTORER}", flush=True)
        else:
            try:
                out = t_restorer(src)
            except Exception as e:
                out = None
                fail(RESTORER, f"transform error: {e}")
            if not out or "rh-batch4:agent-full" not in out:
                if not FAILURES:
                    fail(RESTORER, "anchor not found")
            else:
                p.write_text(out, encoding="utf-8")
                print(f"patched: {RESTORER}", flush=True)
    if FAILURES:
        print("batch4 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
        return 1
    print("batch4 patches applied", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
