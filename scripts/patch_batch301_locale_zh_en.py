import os
import shutil

MARK = "rhLocaleZhEn301"
GRADLE = "app/build.gradle.kts"
RES = "app/src/main/res"
KEEP = ("values", "values-zh", "values-zh-rTW")
DROP = ("values-ar", "values-ja", "values-ko-rKR", "values-ru")
DIAG = "ci_diag_batch301_locale_zh_en.txt"

Q = chr(34)
NL = chr(10)
LOCALE_LINE = "        localeFilters += listOf(" + Q + "zh" + Q + ", " + Q + "en" + Q + ")"
MARK_LINE = "        // " + MARK + ": keep only Chinese (zh) and English (en) resources in packaged builds."
LOG = []


def write_diag():
    with open(DIAG, "w", encoding="utf-8") as f:
        f.write(NL.join(LOG) + NL)


def note(msg):
    print("::notice title=locale-zh-en::" + msg)
    LOG.append("OK " + msg)


def fail(msg):
    print("::error title=locale-zh-en::" + msg)
    LOG.append("FAIL " + msg)
    write_diag()
    raise SystemExit(1)


def insert_locale_filter(src):
    lines = src.split(NL)
    start = -1
    i = 0
    while i < len(lines):
        if lines[i].strip() == "androidResources {":
            start = i
            break
        i = i + 1
    if start < 0:
        fail("androidResources block not found")
    end = -1
    j = start + 1
    while j < len(lines):
        if lines[j].startswith("    }"):
            end = j
            break
        j = j + 1
    if end < 0:
        fail("androidResources block end not found")
    has_gen = False
    k = start + 1
    while k < end:
        if lines[k].strip() == "generateLocaleConfig = true":
            has_gen = True
        k = k + 1
    if not has_gen:
        fail("generateLocaleConfig = true not inside androidResources")
    out = []
    m = 0
    while m < len(lines):
        if m == end:
            out.append(MARK_LINE)
            out.append(LOCALE_LINE)
        out.append(lines[m])
        m = m + 1
    return NL.join(out)


def main():
    if not os.path.isfile(GRADLE):
        fail("missing " + GRADLE)
    with open(GRADLE, "r", encoding="utf-8") as f:
        src = f.read()
    if MARK in src:
        note("gradle already patched, skip insert")
    elif "localeFilters +=" in src:
        note("localeFilters already present without marker, skip insert")
    else:
        out = insert_locale_filter(src)
        with open(GRADLE, "w", encoding="utf-8") as f:
            f.write(out)
        note("inserted localeFilters into " + GRADLE)
    with open(GRADLE, "r", encoding="utf-8") as f:
        after = f.read()
    if LOCALE_LINE not in after:
        fail("localeFilters line missing after write")
    if after.count(MARK) != 1:
        fail("marker must appear exactly once")
    if after.count("(") - after.count(")") != src.count("(") - src.count(")"):
        fail("parenthesis balance changed")
    removed = []
    for name in DROP:
        p = os.path.join(RES, name)
        if os.path.isdir(p):
            shutil.rmtree(p)
            removed.append(name)
    if len(removed) > 0:
        note("removed " + ",".join(removed))
    else:
        note("no extra locale dirs present")
    for name in KEEP:
        if not os.path.isdir(os.path.join(RES, name)):
            fail("kept dir missing: " + name)
    for name in DROP:
        if os.path.isdir(os.path.join(RES, name)):
            fail("drop dir still present: " + name)
    LOG.append("localeFilters=zh,en")
    LOG.append("kept=" + ",".join(KEEP))
    LOG.append("dropped=" + ",".join(DROP))
    write_diag()
    print("::notice title=locale-zh-en::batch301 finished")


main()
