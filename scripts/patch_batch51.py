#!/usr/bin/env python3
'''batch51: 上游易做项 E+F+G 合组（计划：上游移植-易做项计划.md）

E (9f02586d, 2.5.5) 技能导入修复：
  - downloadText → downloadBytes（ByteArray，二进制附属文件不再被 UTF-8 解码损坏）
  - GitHub API 限流（403/429 + X-RateLimit-Remaining==0）给出明确报错
  - saveSkillFilesAtomically → saveSkillFileBytesAtomically（fork SkillManager 已有 bytes 版，已验证）
  - SkillManager.saveSkillFile 的临时文件+rename 部分 fork 已有等价实现（saveSkill 已原子化）→ 不做

F (513b784c, 2.5.2) 翻译快捷入口：
  - AndroidManifest.xml 加 TRANSLATE intent-filter
  - RouteActivity: ShareHandler Composable → handleIntent 函数 + pendingIntents 队列
  - ic_translate.xml 新 drawable + shortcuts.xml 加 translator 快捷方式

G (7038e981, 2.5.1) 工作区 HTML/SVG 预览：
  - WorkspaceFileEditorPage: 加 WebView 预览（源码/预览切换按钮）
  - WorkspaceDetailPage: svg 文件点击 → 打开编辑器（预览）

锚点策略：所有锚点在 CI 上从 fresh checkout 重新应用，必须锚 fork 仓库的恒定形态。
铁律执行：零反斜杠；import 全 'import ' 前缀；自检断言新内容在场。
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
I8 = '        '
I12 = '            '
I16 = '                '
I20 = '                    '
I24 = '                        '

# ============================================================
# E. SkillsVM.kt — downloadText → downloadBytes + 限流报错
# ============================================================
VM = 'app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/skills/SkillsVM.kt'

t = (ROOT / VM).read_text(encoding='utf-8')
if 'rhSkillImportBytes' not in t:
    # E1: SKILL.md 下载
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
        fail_e(VM, 'E1 skillMd download anchor not found')
    t = t.replace(OLD_E1, NEW_E1, 1)

    # E2: 文件循环
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
    if OLD_E2 not in E2 fail_e(VM, 'E2 file loop anchor not found')
    t = t.replace(OLD_E2, NEW_E2, 1)

    # E3: listFilesRecursively 里的 downloadText
    OLD_E3 = '        val json = downloadText(apiUrl) ?: return false'
    NEW_E3 = '        val json = downloadBytes(apiUrl)?.toString(Charsets.UTF_8) ?: return false'
    if OLD_E3 not in t:
        fail_e(VM, 'E3 listFilesRecursively anchor not found')
    t = t.replace(OLD_E3, NEW_E3, 1)

    # E4: downloadText 函数本体 → downloadBytes
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
        fail_e(VM, 'E4 downloadText body anchor not found')
    t = t.replace(OLD_E4, NEW_E4, 1)

    (ROOT / VM).write_text(t, encoding='utf-8')
    print('batch51: E (skills import bytes) OK')
else:
    print('batch51: E already applied')

ROOT2 = None
