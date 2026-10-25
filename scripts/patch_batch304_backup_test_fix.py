import os

DECODER = "app/src/main/java/me/rerere/rikkahub/data/sync/SettingsBackupDecoder.kt"
MIGRATOR = "app/src/main/java/me/rerere/rikkahub/data/datastore/migration/SettingsJsonMigrator.kt"
DIAG = "ci_diag_batch304_backup_test_fix.txt"

Q = chr(34)
NL = chr(10)
LOG = []


def write_diag():
    with open(DIAG, "w", encoding="utf-8") as f:
        f.write(NL.join(LOG) + NL)


def note(msg):
    print("::notice title=backup-compat::" + msg)
    LOG.append("OK " + msg)


def fail(msg):
    print("::error title=backup-compat::" + msg)
    LOG.append("FAIL " + msg)
    write_diag()
    raise SystemExit(1)


def read(path):
    if not os.path.isfile(path):
        fail("missing " + path)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    src = read(DECODER)
    old = "val migrated = SettingsJsonMigrator.migrate(raw)"
    new = "val migrated = runCatching { SettingsJsonMigrator.migrate(raw) }.getOrDefault(raw)"
    if new in src:
        note("decoder already wraps migrate")
    else:
        if src.count(old) != 1:
            fail("decoder migrate line count != 1")
        out = src.replace(old, new, 1)
        if out.count("(") - out.count(")") != src.count("(") - src.count(")"):
            fail("decoder paren balance changed")
        if out.count("{") - out.count("}") != src.count("{") - src.count("}"):
            fail("decoder brace balance changed")
        write(DECODER, out)
        note("decoder wraps migrate")

    src2 = read(MIGRATOR)
    old2 = "Log.e(TAG, " + Q + "migrate: Failed to migrate settings JSON, using original" + Q + ", it)"
    new2 = "runCatching { Log.e(TAG, " + Q + "migrate: Failed to migrate settings JSON, using original" + Q + ", it) }"
    if "runCatching { Log.e(TAG" in src2:
        note("migrator already wraps Log.e")
    else:
        if src2.count(old2) != 1:
            fail("migrator Log.e line count != 1")
        out2 = src2.replace(old2, new2, 1)
        if out2.count("(") - out2.count(")") != src2.count("(") - src2.count(")"):
            fail("migrator paren balance changed")
        if out2.count("{") - out2.count("}") != src2.count("{") - src2.count("}"):
            fail("migrator brace balance changed")
        write(MIGRATOR, out2)
        note("migrator wraps Log.e")
    write_diag()
    print("::notice title=backup-compat::batch304 finished")


main()
