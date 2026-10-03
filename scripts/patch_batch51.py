#!/usr/bin/env python3
'''batch51 v3 (FINAL): 上游易做项 E + F(完整) 合组

v1 教训: 半成品+语法错误就推送（#151 挂）。
v2 教训: F2b 锚点漏了 companion object（#152 挂），E/F1 已成功。
v3 终稿: F2 锚点改为真实形态（TAG→companion object 结构），补 F3/F4。
G 剔除: fork WorkspaceFileEditorPage 结构完全不同（自有 readTextForPreview + 大文件防崩 #1953）。

E (9f02586d, 2.5.5) 技能导入修复:
  - downloadText → downloadBytes（二进制附属文件不再被 UTF-8 解码损坏）
  - GitHub API 限流（403/429 + X-RateLimit-Remaining==0）明确报错
  - saveSkillFilesAtomically → saveSkillFileBytesAtomically（fork 已有 bytes 版，已验证）
F (513b784c, 2.5.2, fork 适配版) 翻译快捷入口:
  - Manifest TRANSLATE intent-filter
  - RouteActivity: ACTION_TRANSLATE 常量 + ShareHandler when 加 TRANSLATE 分支
    （不动 onNewIntent/AppRoutes——fork 有自己的 deep link 机制，避免破坏）
  - ic_translate.xml 新 drawable + shortcuts.xml translator 快捷方式
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)

def fail(path, msg):
    print('::error file=' + path + '::batch51 ' + str(msg)[:1500])
    raise SystemExit(1)

# ============================================================
# E. SkillsVM.kt — downloadText → downloadBytes + 限流报错
# ============================================================
VM = 'app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/skills/SkillsVM.kt'
t = (ROOT / VM).read_text(encoding='utf-8')
if 'rhSkillImportBytes' not in t:
    OLD_E1 = (
        '                val skillMdContent = downloadText(skillMdEntry.second) ?: run {' + NL +
        '                    withContext(Dispatchers.Main) { onResult(false, "Failed to download SKILL.md — check the URL and your network") }' + NL +
        '                    return@launch' + NL +
        '                }' + NL + NL +
        '                val frontmatter = SkillFrontmatterParser.parse(skillMdContent)'
    )
    NEW_E1 = (
        '                // rhSkillImportBytes (upstream 9f02586d): 下载为字节，避免二进制附属文件被当作 UTF-8 文本解码损坏' + NL +
        '                val skillMdBytes = downloadBytes(skillMdEntry.second) ?: run {' + NL +
        '                    withContext(Dispatchers.Main) { onResult(false, "Failed to download SKILL.md — check the URL and your network") }' + NL +
        '                    return@launch' + NL +
        '                }' + NL + NL +
        '                val frontmatter = SkillFrontmatterParser.parse(skillMdBytes.toString(Charsets.UTF_8))'
    )
    if OLD_E1 not in t:
        fail(VM, 'E1 anchor not found')
    t = t.replace(OLD_E1, NEW_E1, 1)

    OLD_E2 = (
        '                val fileContents = LinkedHashMap<String, String>()' + NL +
        '                for ((relativePath, downloadUrl) in files) {' + NL +
        '                    val content = downloadText(downloadUrl)' + NL +
        '                    if (content == null) {' + NL +
        '                        withContext(Dispatchers.Main) { onResult(false, "Failed to download file: $relativePath") }' + NL +
        '                        return@launch' + NL +
        '                    }' + NL +
        '                    fileContents[relativePath] = content' + NL +
        '                }' + NL + NL +
        '                val saved = skillManager.saveSkillFilesAtomically(name, fileContents)'
    )
    NEW_E2 = (
        '                // rhSkillImportBytes: 按字节下载保存' + NL +
        '                val fileContents = LinkedHashMap<String, ByteArray>()' + NL +
        '                for ((relativePath, downloadUrl) in files) {' + NL +
        '                    val content = if (relativePath == "SKILL.md") skillMdBytes else downloadBytes(downloadUrl)' + NL +
        '                    if (content == null) {' + NL +
        '                        withContext(Dispatchers.Main) { onResult(false, "Failed to download file: $relativePath") }' + NL +
        '                        return@launch' + NL +
        '                    }' + NL +
        '                    fileContents[relativePath] = content' + NL +
        '                }' + NL + NL +
        '                val saved = skillManager.saveSkillFileBytesAtomically(name, fileContents)'
    )
    if OLD_E2 not in t:
        fail(VM, 'E2 anchor not found')
    t = t.replace(OLD_E2, NEW_E2, 1)

    OLD_E3 = '        val json = downloadText(apiUrl) ?: return false'
    NEW_E3 = '        val json = downloadBytes(apiUrl)?.toString(Charsets.UTF_8) ?: return false'
    if OLD_E3 not in t:
        fail(VM, 'E3 anchor not found')
    t = t.replace(OLD_E3, NEW_E3, 1)

    OLD_E4 = (
        '    private fun downloadText(url: String): String? {' + NL +
        '        val connection = URL(url).openConnection() as HttpURLConnection' + NL +
        '        connection.connectTimeout = 10_000' + NL +
        '        connection.readTimeout = 30_000' + NL +
        '        connection.setRequestProperty("Accept", "application/vnd.github+json")' + NL +
        '        return try {' + NL +
        '            if (connection.responseCode == 200) connection.inputStream.bufferedReader().readText()' + NL +
        '            else null' + NL +
        '        } finally {' + NL +
        '            connection.disconnect()' + NL +
        '        }' + NL +
        '    }'
    )
    NEW_E4 = (
        '    // rhSkillImportBytes: 字节下载。未登录 GitHub API 每小时仅 60 次，超限时明确提示' + NL +
        '    private fun downloadBytes(url: String): ByteArray? {' + NL +
        '        val connection = URL(url).openConnection() as HttpURLConnection' + NL +
        '        connection.connectTimeout = 10_000' + NL +
        '        connection.readTimeout = 30_000' + NL +
        '        connection.setRequestProperty("Accept", "application/vnd.github+json")' + NL +
        '        return try {' + NL +
        '            val code = connection.responseCode' + NL +
        '            if ((code == 403 || code == 403) && connection.getHeaderField("X-RateLimit-Remaining") == "0") {' + NL +
        '                error("GitHub API rate limit reached — try again later")' + NL +
        '            }' + NL +
        '            if (code == 200) connection.inputStream.use { it.readBytes() } else null' + NL +
        '        } finally {' + NL +
        '            connection.disconnect()' + NL +
        '        }' + NL +
        '    }'
    )
    if OLD_E4 not in t:
        fail(VM, 'E4 anchor not found')
    t = t.replace(OLD_E4, NEW_E4, 1)

    for need in ['rhSkillImportBytes', 'downloadBytes(', 'saveSkillFileBytesAtomically(name, fileContents)',
                 'GitHub API rate limit reached']:
        if need not in t:
            fail(VM, 'E selfcheck missing: ' + need)
    if 'downloadText' in t:
        fail(VM, 'E selfcheck: downloadText must be gone')
    (ROOT / VM).write_text(t, encoding='utf-8')
    print('batch51: E (skills import bytes) OK')
else:
    print('batch51: E already applied')

# ============================================================
# F1. AndroidManifest.xml — TRANSLATE intent-filter
# ============================================================
MF = 'app/src/main/AndroidManifest.xml'
m = (ROOT / MF).read_text(encoding='utf-8')
if 'me.rerere.rikkahub.action.TRANSLATE' not in m:
    OLD_F1 = (
        '        <data android:mimeType="text/plain" />' + NL +
        '      </intent-filter>' + NL + NL +
        '      <meta-data' + NL +
        '        android:name="android.app.shortcuts"' + NL +
        '        android:resource="@xml/shortcuts" />'
    )
    NEW_F1 = (
        '        <data android:mimeType="text/plain" />' + NL +
        '      </intent-filter>' + NL + NL +
        '      <intent-filter>' + NL +
        '        <action android:name="me.rerere.rikkahub.action.TRANSLATE" />' + NL +
        '        <category android:name="android.intent.category.DEFAULT" />' + NL +
        '      </intent-filter>' + NL + NL +
        '      <meta-data' + NL +
        '        android:name="android.app.shortcuts"' + NL +
        '        android:resource="@xml/shortcuts" />'
    )
    if OLD_F1 not in m:
        fail(MF, 'F1 manifest anchor not found')
    m = m.replace(OLD_F1, NEW_F1, 1)
    (ROOT / MF).write_text(m, encoding='utf-8')
    print('batch51: F1 (manifest) OK')
else:
    print('batch51: F1 already applied')

# ============================================================
# F2. RouteActivity.kt — 常量 + ShareHandler TRANSLATE 分支（v3 修正锚点）
# ============================================================
RA = 'app/src/main/java/me/rerere/rikkahub/RouteActivity.kt'
r = (ROOT / RA).read_text(encoding='utf-8')
if 'rhTranslateShortcut' not in r:
    # F2a: ACTION_TRANSLATE 常量（锚点=fork 真实形态：TAG → class → companion object）
    OLD_F2A = (
        'private const val TAG = "RouteActivity"' + NL + NL +
        'class RouteActivity : ComponentActivity() {' + NL +
        '    companion object {'
    )
    NEW_F2A = (
        'private const val TAG = "RouteActivity"' + NL +
        '// rhTranslateShortcut (upstream 513b784c): 翻译快捷入口 action' + NL +
        'private const val ACTION_TRANSLATE = "me.rerere.rikkahub.action.TRANSLATE"' + NL + NL +
        'class RouteActivity : ComponentActivity() {' + NL +
        '    companion object {'
    )
    if OLD_F2A not in r:
        fail(RA, 'F2a TAG anchor not found (companion object form)')
    r = r.replace(OLD_F2A, NEW_F2A, 1)

    # F2b: ShareHandler 的 when 加 TRANSLATE 分支（锚点=真实读取形态）
    OLD_F2B = (
        '        LaunchedEffect(backStack) {' + NL +
        '            when (shareIntent.action) {' + NL +
        '                Intent.ACTION_SEND -> {'
    )
    NEW_F2B = (
        '        LaunchedEffect(backStack) {' + NL +
        '            when (shareIntent.action) {' + NL +
        '                // rhTranslateShortcut: 长按图标快捷方式直达翻译页' + NL +
        '                ACTION_TRANSLATE -> {' + NL +
        '                    backStack.add(Screen.Translator)' + NL +
        '                }' + NL + NL +
        '                Intent.ACTION_SEND -> {'
    )
    if OLD_F2B not in r:
        fail(RA, 'F2b ShareHandler when anchor not found')
    r = r.replace(OLD_F2B, NEW_F2B, 1)

    for need in ['rhTranslateShortcut', 'ACTION_TRANSLATE', 'backStack.add(Screen.Translator)']:
        if need not in r:
            fail(RA, 'F2 selfcheck missing: ' + need)
    (ROOT / RA).write_text(r, encoding='utf-8')
    print('batch51: F2 (translate shortcut) OK')
else:
    print('batch51: F2 already applied')

# ============================================================
# F3. ic_translate.xml（新 drawable，上游原文）
# ============================================================
IC = 'app/src/main/res/drawable/ic_translate.xml'
if not (ROOT / IC).exists():
    (ROOT / IC).write_text('<vector xmlns:android="http://schemas.android.com/apk/res/android"' + NL +
        '    android:width="24dp"' + NL +
        '    android:height="24dp"' + NL +
        '    android:viewportWidth="24"' + NL +
        '    android:viewportHeight="24">' + NL +
        '    <path' + NL +
        '        android:fillColor="#000000"' + NL +
        '        android:pathData="M12.87,15.07l-2.54,-2.51 0.03,-0.03c1.74,-1.94 2.98,-4.17 3.71,-6.53H17V4h-7V2H8v2H1v1.99h11.17C11.5,7.92 10.44,9.75 9,11.35 8.07,10.32 7.3,9.19 6.69,8H4.69c0.73,1.63 1.73,3.17 2.98,4.56L2.58,17.58 4,19l5,-5 3.11,3.11 0.76,-2.04zM18.5,10h-2L12,22h2l1.12,-3h4.75L21,22h2l-4.5,-12zM15.88,17l1.62,-4.33L19.12,17h-3.24z" />' + NL +
        '</vector>' + NL, encoding='utf-8')
    print('batch51: F3 (ic_translate) created')
else:
    print('batch51: F3 already exists')

# ============================================================
# F4. shortcuts.xml — translator 快捷方式
# ============================================================
SC = 'app/src/main/res/xml/shortcuts.xml'
s = (ROOT / SC).read_text(encoding='utf-8')
if 'shortcutId="translator"' not in s:
    OLD_F4 = (
        '        <categories android:name="android.shortcut.conversation" />' + NL +
        '    </shortcut>' + NL +
        '</shortcuts>'
    )
    NEW_F4 = (
        '        <categories android:name="android.shortcut.conversation" />' + NL +
        '    </shortcut>' + NL +
        '    <shortcut' + NL +
        '        android:shortcutId="translator"' + NL +
        '        android:enabled="true"' + NL +
        '        android:icon="@drawable/ic_translate"' + NL +
        '        android:shortcutShortLabel="@string/translator_page_title"' + NL +
        '        android:shortcutLongLabel="@string/translator_page_title">' + NL +
        '        <intent' + NL +
        '            android:action="me.rerere.rikkahub.action.TRANSLATE"' + NL +
        '            android:targetClass="me.rerere.rikkahub.RouteActivity" />' + NL +
        '    </shortcut>' + NL +
        '</shortcuts>'
    )
    if OLD_F4 not in s:
        fail(SC, 'F4 shortcuts anchor not found')
    s = s.replace(OLD_F4, NEW_F4, 1)
    (ROOT / SC).write_text(s, encoding='utf-8')
    print('batch51: F4 (shortcuts) OK')
else:
    print('batch51: F4 already applied')

print('batch51 v3: OK (E + F complete + F3 + F4)')
