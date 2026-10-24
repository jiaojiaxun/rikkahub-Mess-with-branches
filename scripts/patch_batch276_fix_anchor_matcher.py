#!/usr/bin/env python3
# batch276: repair the anchor matcher used by batch271/272/273/275 and re-run them in place.
#
# Root cause of run#494's 8 failures: insert_after_line compared `line.strip()` against an
# anchor that still carried its own leading indentation, so the comparison could never match
# (anchor count=0). Fix = strip BOTH sides, then re-execute the four phase scripts. Every
# edit is guarded by its own MARK, so already-landed files are skipped and only the failed
# ones are written. Safe to run repeatedly.
# MARK=rhAnchorFix276
import sys
from pathlib import Path

MARK = "rhAnchorFix276"
NL = chr(10)
Q = chr(34)
DIAG = "ci_diag_batch276.txt"
SCRIPTS = [
    "scripts/patch_batch271_approval_identity.py",
    "scripts/patch_batch272_appcontrol_actions.py",
    "scripts/patch_batch273_mcp_server_grants_ui.py",
    "scripts/patch_batch275_heart_rate_share.py",
]
fixed = []
reran = []
failed = []


def diag(msg):
    try:
        with open(DIAG, "a", encoding="utf-8") as f:
            f.write(msg + NL)
    except Exception:
        pass


def fail(msg):
    diag("FAIL " + msg)
    print("::error title=batch276::" + msg)
    raise SystemExit(0)


def fix_matcher(path):
    p = Path(path)
    if not p.exists():
        fail("missing script: " + path)
    text = p.read_text(encoding="utf-8")
    old = "line.strip() == anchor"
    new = "line.strip() == anchor.strip()"
    n = text.count(old)
    if n == 0:
        diag("already fixed (or no matcher): " + path)
        return
    p.write_text(text.replace(old, new), encoding="utf-8")
    fixed.append(Path(path).name + ":" + str(n))


def fix_cron_description():
    path = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/CronTools.kt"
    p = Path(path)
    if not p.exists():
        fail("missing file: " + path)
    text = p.read_text(encoding="utf-8")
    old = "Presets: " + Q + Q + " + CronPresets.ids()."
    new = "Presets: ${CronPresets.ids()}."
    if old not in text:
        diag("cron description literal not found (already fixed?)")
        return
    text = text.replace(old, new, 1)
    p.write_text(text, encoding="utf-8")
    fixed.append("cron-description-interp")


def rerun(path):
    p = Path(path)
    if not p.exists():
        fail("missing script for rerun: " + path)
    code = p.read_text(encoding="utf-8")
    with open(DIAG, "a", encoding="utf-8") as f:
        f.write("=== rerun " + Path(path).name + " ===" + NL)
    try:
        exec(compile(code, path, "exec"), {"__name__": "__main__", "__file__": path})
        reran.append(Path(path).name)
    except SystemExit:
        reran.append(Path(path).name + "(exit)")
    except Exception as e:
        diag("EXCEPTION rerun " + path + ": " + repr(e))
        failed.append(Path(path).name)


def main():
    for path in SCRIPTS:
        try:
            fix_matcher(path)
        except SystemExit:
            failed.append(path)
        except Exception as e:
            diag("EXCEPTION fix " + path + ": " + repr(e))
            failed.append(path)

    try:
        fix_cron_description()
    except SystemExit:
        failed.append("cron-description")
    except Exception as e:
        diag("EXCEPTION cron-description: " + repr(e))
        failed.append("cron-description")

    for path in SCRIPTS:
        if path in failed:
            continue
        rerun(path)

    diag("fixed=" + ",".join(fixed))
    diag("reran=" + ",".join(reran))
    diag("failed=" + ((",".join(failed)) if failed else "none"))
    if failed:
        print("::error title=batch276-FAILED::" + ",".join(failed))
    else:
        print("::notice title=batch276-ok::fixed=" + str(len(fixed)) + " reran=" + str(len(reran)))


main()
