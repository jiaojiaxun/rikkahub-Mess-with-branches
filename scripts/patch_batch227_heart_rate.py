#!/usr/bin/env python3
# batch227: BLE heart-rate broadcast entry in the chat input "+" sheet.
# New ListItem in FilesPicker.kt between Extensions and Compress History.
# New files (data/ble/HeartRateMonitor.kt, ui/components/ai/HeartRateDialog.kt)
# are committed directly; this script only edits existing files.
# MARK=rhHeartRate
import sys
from pathlib import Path

MARK = "rhHeartRate"
NL = chr(10)
Q = chr(34)
applied = []

MANIFEST = "app/src/main/AndroidManifest.xml"
STR_EN = "app/src/main/res/values/strings.xml"
STR_ZH = "app/src/main/res/values-zh/strings.xml"
FILESPICKER = "app/src/main/java/me/rerere/rikkahub/ui/components/ai/FilesPicker.kt"

EN_STRINGS = [
    ("heart_rate_title", "Live Heart Rate"),
    ("heart_rate_bpm_unit", "BPM"),
    ("heart_rate_connected_to", "Connected: %1$s"),
    ("heart_rate_connecting", "Connecting..."),
    ("heart_rate_scanning", "Scanning..."),
    ("heart_rate_not_connected", "Not connected"),
    ("heart_rate_last_update", "Last update: %1$s"),
    ("heart_rate_permission_hint", "Bluetooth permission is needed to receive the heart-rate broadcast."),
    ("heart_rate_grant_permission", "Grant"),
    ("heart_rate_bluetooth_off", "Bluetooth is off."),
    ("heart_rate_no_devices", "No devices found. Enable heart-rate broadcast on the watch first."),
    ("heart_rate_last_device", "Last device: %1$s"),
    ("heart_rate_connect", "Connect"),
    ("heart_rate_disconnect", "Disconnect"),
    ("heart_rate_scan", "Scan"),
    ("heart_rate_stop_scan", "Stop"),
    ("heart_rate_close", "Close"),
]

ZH_STRINGS = [
    ("heart_rate_title", "实时心率"),
    ("heart_rate_bpm_unit", "BPM"),
    ("heart_rate_connected_to", "已连接：%1$s"),
    ("heart_rate_connecting", "连接中..."),
    ("heart_rate_scanning", "扫描中..."),
    ("heart_rate_not_connected", "未连接"),
    ("heart_rate_last_update", "最后更新：%1$s"),
    ("heart_rate_permission_hint", "需要蓝牙权限才能接收心率广播"),
    ("heart_rate_grant_permission", "授权"),
    ("heart_rate_bluetooth_off", "蓝牙未开启"),
    ("heart_rate_no_devices", "没有发现设备，请先在手表上开启「心率广播」"),
    ("heart_rate_last_device", "上次设备：%1$s"),
    ("heart_rate_connect", "连接"),
    ("heart_rate_disconnect", "断开连接"),
    ("heart_rate_scan", "扫描"),
    ("heart_rate_stop_scan", "停止扫描"),
    ("heart_rate_close", "关闭"),
]


def fail(msg):
    print("::error title=batch227::" + msg)
    sys.exit(0)


def read(path):
    p = Path(path)
    if not p.exists():
        fail("missing file: " + path)
    return p.read_text(encoding="utf-8")


def write(path, content):
    Path(path).write_text(content, encoding="utf-8")


def insert_after_exact(content, anchor, block, label):
    lines = content.split(NL)
    for i, line in enumerate(lines):
        if line.strip() == anchor:
            lines.insert(i + 1, block)
            applied.append(label)
            return NL.join(lines)
    fail(label + " anchor not found: [" + anchor + "]")
    return content


def insert_before_exact(content, anchor, block, label):
    lines = content.split(NL)
    idx = -1
    for i, line in enumerate(lines):
        if line.strip() == anchor:
            idx = i
            break
    if idx < 0:
        fail(label + " anchor not found: [" + anchor + "]")
    lines.insert(idx, block)
    applied.append(label)
    return NL.join(lines)


def xml_string(name, text):
    return "    <string name=" + Q + name + Q + ">" + text + "</string>"


# --- AndroidManifest.xml: BLUETOOTH_SCAN / BLUETOOTH_CONNECT ---
content = read(MANIFEST)
if MARK in content:
    print("skip manifest (marker present)")
else:
    mblock = "  <!-- " + MARK + " -->"
    mblock += NL + "  <uses-permission android:name=" + Q + "android.permission.BLUETOOTH" + Q
    mblock += " android:maxSdkVersion=" + Q + "30" + Q + " />"
    mblock += NL + "  <uses-permission android:name=" + Q + "android.permission.BLUETOOTH_ADMIN" + Q
    mblock += " android:maxSdkVersion=" + Q + "30" + Q + " />"
    mblock += NL + "  <uses-permission"
    mblock += NL + "    android:name=" + Q + "android.permission.BLUETOOTH_SCAN" + Q
    mblock += NL + "    android:usesPermissionFlags=" + Q + "neverForLocation" + Q + " />"
    mblock += NL + "  <uses-permission android:name=" + Q + "android.permission.BLUETOOTH_CONNECT" + Q + " />"
    mblock += NL + "  <uses-feature android:name=" + Q + "android.hardware.bluetooth_le" + Q
    mblock += " android:required=" + Q + "false" + Q + " />"
    content = insert_after_exact(
        content,
        "<uses-permission android:name=" + Q + "android.permission.RECORD_AUDIO" + Q + " />",
        mblock,
        "manifest",
    )
    write(MANIFEST, content)

# --- strings.xml (en / zh) ---
for path, pairs, label in ((STR_EN, EN_STRINGS, "strings-en"), (STR_ZH, ZH_STRINGS, "strings-zh")):
    content = read(path)
    if MARK in content:
        print("skip " + label + " (marker present)")
        continue
    block = "    <!-- " + MARK + " -->"
    for sname, stext in pairs:
        block += NL + xml_string(sname, stext)
    content = insert_before_exact(content, "</resources>", block, label)
    write(path, content)

# --- FilesPicker.kt: import + menu item between Extensions and Compress History ---
menu_block = "        // " + MARK + ": live heart-rate broadcast entry"
menu_block += NL + "        var showHeartRateDialog by remember { mutableStateOf(false) }"
menu_block += NL + "        ListItem("
menu_block += NL + "            leadingContent = {"
menu_block += NL + "                Icon("
menu_block += NL + "                    imageVector = HugeIcons.Pulse01,"
menu_block += NL + "                    contentDescription = stringResource(R.string.heart_rate_title),"
menu_block += NL + "                )"
menu_block += NL + "            },"
menu_block += NL + "            headlineContent = {"
menu_block += NL + "                Text(stringResource(R.string.heart_rate_title))"
menu_block += NL + "            },"
menu_block += NL + "            colors = ListItemDefaults.colors("
menu_block += NL + "                containerColor = MaterialTheme.colorScheme.surfaceContainer"
menu_block += NL + "            ),"
menu_block += NL + "            modifier = Modifier"
menu_block += NL + "                .clip(MaterialTheme.shapes.large)"
menu_block += NL + "                .clickable {"
menu_block += NL + "                    showHeartRateDialog = true"
menu_block += NL + "                },"
menu_block += NL + "        )"
menu_block += NL + "        if (showHeartRateDialog) {"
menu_block += NL + "            HeartRateDialog(onDismiss = { showHeartRateDialog = false })"
menu_block += NL + "        }"

content = read(FILESPICKER)
if MARK in content:
    print("skip filespicker (marker present)")
else:
    brace_before = content.count("{") - content.count("}")
    paren_before = content.count("(") - content.count(")")
    if "import me.rerere.hugeicons.stroke.Pulse01" not in content:
        content = insert_after_exact(
            content,
            "import me.rerere.hugeicons.stroke.Package01",
            "import me.rerere.hugeicons.stroke.Pulse01",
            "fp-import",
        )
    content = insert_before_exact(content, "// Compress History Button", menu_block, "fp-menu")
    brace_after = content.count("{") - content.count("}")
    paren_after = content.count("(") - content.count(")")
    if brace_before != brace_after or paren_before != paren_after:
        fail("brace/paren balance changed in FilesPicker.kt")
    write(FILESPICKER, content)

# --- verify ---
for path in (MANIFEST, STR_EN, STR_ZH, FILESPICKER):
    if MARK not in read(path):
        fail("verify failed: marker missing in " + path)

report = ""
for item in applied:
    if report:
        report += ", "
    report += item
if report:
    print("::error title=batch227-report::applied=[" + report + "]")
else:
    print("::error title=batch227-report::nothing applied (already present?)")
