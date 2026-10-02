from pathlib import Path
import re

ROOT = Path.cwd()

def fail(path, msg):
    print(f"::error file={path}::batch33 {msg[:1400]}")
    raise SystemExit(1)

# 1) build.gradle.kts
P1 = "app/build.gradle.kts"
t1 = (ROOT / P1).read_text(encoding="utf-8")
if "work-runtime-ktx" not in t1:
    A = '    implementation(libs.androidx.documentfile)\n'
    B = A + '    implementation("androidx.work:work-runtime-ktx:2.9.1")\n'
    if t1.count(A) != 1: fail(P1, "docfile anchor count error")
    (ROOT / P1).write_text(t1.replace(A, B), encoding="utf-8")

# 2) AndroidManifest.xml
P2 = "app/src/main/AndroidManifest.xml"
t2 = (ROOT / P2).read_text(encoding="utf-8")
if "RECEIVE_BOOT_COMPLETED" not in t2:
    A = '  <uses-permission android:name="android.permission.NFC" />\n'
    B = A + '  <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />\n'
    t2 = t2.replace(A, B)
    # Receiver block
    SAFE_RE = re.compile(r"(?P<line>.*SafeModeActivity.*theme=\"@style/Theme\.Rikkahub\"[ \t]*/>[ \t]*\n)", re.DOTALL)
    m = SAFE_RE.search(t2)
    if not m: fail(P2, "SafeModeActivity anchor not found")
    ins = (
        "    <receiver android:name=\".service.CronBootReceiver\" android:exported=\"true\">\n"
        "      <intent-filter>\n"
        "        <action android:name=\"android.intent.action.BOOT_COMPLETED\" />\n"
        "        <action android:name=\"android.intent.action.MY_PACKAGE_REPLACED\" />\n"
        "      </intent-filter>\n"
        "    </receiver>\n"
    )
    (ROOT / P2).write_text(t2[:m.end()] + ins + t2[m.end():], encoding="utf-8")
