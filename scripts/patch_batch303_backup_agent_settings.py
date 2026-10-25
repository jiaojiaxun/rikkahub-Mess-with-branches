import os

RESTORER = "app/src/main/java/me/rerere/rikkahub/data/sync/webdav/BackupArchiveRestorer.kt"
DIAG = "ci_diag_batch303_backup_agent_settings.txt"

Q = chr(34)
NL = chr(10)
LOG = []
MARK = "agentSettings = SettingsBackupDecoder.decode("


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


def main():
    if not os.path.isfile(RESTORER):
        fail("missing " + RESTORER)
    with open(RESTORER, "r", encoding="utf-8") as f:
        src = f.read()
    if MARK in src:
        note("agent settings already tolerant")
        write_diag()
        return
    lines = src.split(NL)
    idx = -1
    for i in range(len(lines)):
        if "agentSettings = json.decodeFromString(" in lines[i]:
            idx = i
            break
    if idx < 0:
        fail("agentSettings decode line not found")
    if idx + 2 >= len(lines):
        fail("agentSettings block truncated")
    if "SettingsJsonMigrator.migrate(rawAgentSettings" not in lines[idx + 1]:
        fail("agentSettings migrate line mismatch")
    if lines[idx + 2].strip() != ")":
        fail("agentSettings closing paren mismatch")
    line = lines[idx]
    indent = line[: len(line) - len(line.lstrip())]
    block = []
    block.append(indent + "agentSettings = SettingsBackupDecoder.decode(")
    block.append(indent + "    json,")
    block.append(indent + "    rawAgentSettings.toByteArray().toString(Charsets.UTF_8),")
    block.append(indent + ")")
    block.append(indent + "if (agentSettings == null) {")
    block.append(indent + "    Log.w(TAG, " + Q + "agent_settings.json 无法解析，回退到包内兼容设置" + Q + ")")
    block.append(indent + "}")
    lines[idx : idx + 3] = block
    out = NL.join(lines)
    if MARK not in out:
        fail("post-write marker missing")
    if out.count("(") - out.count(")") != src.count("(") - src.count(")"):
        fail("paren balance changed")
    if out.count("{") - out.count("}") != src.count("{") - src.count("}"):
        fail("brace balance changed")
    with open(RESTORER, "w", encoding="utf-8") as f:
        f.write(out)
    LOG.append("compat: FULL archive agent_settings.json also degrades instead of aborting")
    write_diag()
    print("::notice title=backup-compat::batch303 finished")


main()
