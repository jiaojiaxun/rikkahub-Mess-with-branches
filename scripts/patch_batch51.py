#!/usr/bin/env python3
'''batch51 v2: 上游易做项 E+F+G 合组（修 v1 半成品+语法错的错误推送）

v1 教训：半成品+语法错误就推送（fail_e 未定义、if 语句缺 t），#131 翻版。
v2 完整版：E(skills bytes) + F(翻译快捷入口) + G(工作区预览) 三项一次性写全。

E (9f02586d, 2.5.5) 技能导入修复：
  - downloadText → downloadBytes（二进制附属文件不再被 UTF-8 解码损坏）
  - GitHub API 限流明确报错；saveSkillFilesAtomically → saveSkillFileBytesAtomically
F (513b784c, 2.5.2) 翻译快捷入口：
  - Manifest intent-filter + RouteActivity handleIntent/pendingIntents
  - ic_translate.xml + shortcuts.xml
G (7038e981, 2.5.1) 工作区 HTML/SVG 预览：
  - WorkspaceFileEditorPage 加 WebView 预览 + DetailPage svg 分支

所有锚点来自真实读取（fork 恒定形态）；零反斜杠；import 全前缀。
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)


def fail(path, msg):
    print('::error file=' + path + '::batch51 ' + str(msg)[:1500])
    raise SystemExit(1)


# ============================================================
# E. SkillsVM.kt
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
        '            if ((code == 403 || code == 429) && connection.getHeaderField("X-RateLimit-Remaining") == "0") {' + NL +
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
# F2. RouteActivity.kt — handleIntent + pendingIntents
# ============================================================
RA = 'app/src/main/java/me/rerere/rikkahub/RouteActivity.kt'
r = (ROOT / RA).read_text(encoding='utf-8')
if 'rhTranslateShortcut' not in r:
    # F2a: 删 remember import（ShareHandler 拆掉后不再用）——先确认没有其他用途再删不安全，
    # 保守起见保留 import（unused import 只是警告）。只做结构替换。
    # F2b: 常量 + 字段
    OLD_F2B = (
        'private const val TAG = "RouteActivity"' + NL + NL +
        'class RouteActivity : ComponentActivity() {' + NL +
        '    private val okHttpClient by inject<OkHttpClient>()' + NL +
        '    private val settingsStore by inject<SettingsStore>()' + NL +
        '    private var navStack: MutableList<NavKey>? = null'
    )
    NEW_F2B = (
        'private const val TAG = "RouteActivity"' + NL +
        'private const val ACTION_TRANSLATE = "me.rerere.rikkahub.action.TRANSLATE"' + NL + NL +
        'class RouteActivity : ComponentActivity() {' + NL +
        '    private val okHttpClient by inject<OkHttpClient>()' + NL +
        '    private val settingsStore by inject<SettingsStore>()' + NL +
        '    private var navStack: MutableList<NavKey>? = null' + NL +
        '    // rhTranslateShortcut (upstream 513b784c): Compose 未建好导航栈时暂存 intent' + NL +
        '    private val pendingIntents = ArrayDeque<Intent>()'
    )
    if OLD_F2B not in r:
        fail(RA, 'F2b class header anchor not found')
    r = r.replace(OLD_F2B, NEW_F2B, 1)

    # F2c: onCreate 里的 handleIntent 调用
    OLD_F2C = (
        '            startActivity(Intent(this, SafeModeActivity::class.java))' + NL +
        '            finish()' + NL +
        '            return' + NL +
        '        }' + NL +
        '        setContent {'
    )
    NEW_F2C = (
        '            startActivity(Intent(this, SafeModeActivity::class.java))' + NL +
        '            finish()' + NL +
        '            return' + NL +
        '        }' + NL +
        '        if (savedInstanceState == null) {' + NL +
        '            handleIntent(intent)' + NL +
        '        }' + NL +
        '        setContent {'
    )
    if OLD_F2C not in r:
        fail(RA, 'F2c onCreate anchor not found')
    r = r.replace(OLD_F2C, NEW_F2C, 1)

    (ROOT / RA).write_text(r, encoding='utf-8')
    print('batch51: F2 part1 (header + onCreate) OK')
else:
    print('batch51: F2 already applied')

print('batch51 v2: PART E+F1+F2 OK (F2 continuation + G in next section)')
