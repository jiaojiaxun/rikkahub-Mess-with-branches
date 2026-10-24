#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch265b: scripts 进备份（打包 + 恢复解回，两侧一起改）

【用户需求】脚本也要可以存入备份。

【取证结论（batch265a 已 dump，实读确认）】
- `FileFolders` 常量定义在 `FilesManager.kt L489`：
      object FileFolders { UPLOAD="upload", SKILLS="skills", FONTS="fonts",
                           TOOL_OUTPUTS="tool_outputs", IMAGES="images" }
      ⇒ 没有 SCRIPTS 常量，scripts 目录名就是字面量 "scripts"（与 "workspaces" 同款，也不走常量）。
- 备份打包侧 `WebDavSync.backupFileEntries`（L326-330）：
      val trees = if (full) {
          listOf(FileFolders.SKILLS, FileFolders.IMAGES, FileFolders.TOOL_OUTPUTS, "workspaces")
      } else {
          listOf(FileFolders.SKILLS)
      }
      ⇒ 没有 "scripts"。
- 恢复侧 `BackupArchiveRestorer`：
      · 分发链两处：`safeName.startsWith("${FileFolders.TOOL_OUTPUTS}/") -> resolveStagedFile(staging, safeName)`
        （L158 与 L536，内容相同）
      · rootAliases（L366-375）：upload/uploads/files/skills/skill/fonts/images/tool_outputs/tool-outputs/workspaces/workspace
        ⇒ 没有 scripts
      · normalizeEntryName 的守卫集合：`setOf("upload", "uploads", "files", "skills", "skill", "fonts",
        "images", "tool_outputs", "tool-outputs", "workspaces", "workspace")` ⇒ 没有 scripts/script

【本批改动（两个文件，四处）】
1. WebDavSync.backupFileEntries 的 trees 两处都加 "scripts"（FULL 与 LITE 都带脚本）
2. BackupArchiveRestorer 分发链两处都加 `safeName.startsWith("scripts/") -> resolveStagedFile(staging, safeName)`
3. rootAliases 加 `"scripts" to "scripts"` 与 `"script" to "scripts"`
4. normalizeEntryName 的守卫集合加 `"scripts", "script"`

【为什么 FULL 和 LITE 都带】
脚本是用户写的工具逻辑（体积小），不是附件；LITE 只省附件不省脚本，所以两侧都加。

五查:
 1. import 清单: 零新增（FileFolders 已 import；"scripts" 是字面量，与 "workspaces" 同款）
 2. 同文件冲突: WebDavSync.kt 被 batch213/215/216 改过；本批锚点 `val trees = if (full) {`
    与 batch216 的「备份项选择」落点不重叠。BackupArchiveRestorer.kt 被 batch155/156 改过，
    本批锚点在分发链与 rootAliases，不重叠。
 3. 作用域: 全部在既有函数体内
 4. 括号配对: 均为「列表/集合元素追加」，括号 1 对 1 => balance 不变（断言）
 5. 函数签名: 零改动
Python 三查: Q/SQ 变量构造引号; NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 失败即中止不写盘
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
DIAG = 'ci_diag_batch265.txt'

WEBDAV = 'app/src/main/java/me/rerere/rikkahub/data/sync/webdav/WebDavSync.kt'
RESTORER = 'app/src/main/java/me/rerere/rikkahub/data/sync/webdav/BackupArchiveRestorer.kt'

report = []


def note(msg):
    report.append(str(msg)[:900])


def balance(text):
    return (text.count('(') - text.count(')')
            + text.count('{') - text.count('}')
            + text.count('[') - text.count(']'))


class Abort(Exception):
    pass


def patch_webdav():
    p = ROOT / WEBDAV
    if not p.exists():
        note('ABORT missing WebDavSync.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhBackupScripts265' in t:
        note('webdav already applied')
        return
    bal0 = balance(t)

    full_old = 'listOf(FileFolders.SKILLS, FileFolders.IMAGES, FileFolders.TOOL_OUTPUTS, "workspaces")'
    full_new = 'listOf(FileFolders.SKILLS, FileFolders.IMAGES, FileFolders.TOOL_OUTPUTS, "workspaces", "scripts") // rhBackupScripts265'
    lite_old = 'listOf(FileFolders.SKILLS)'
    lite_new = 'listOf(FileFolders.SKILLS, "scripts") // rhBackupScripts265'

    if t.count(full_old) != 1:
        note('ABORT webdav full trees anchor count=' + str(t.count(full_old)))
        raise Abort('webdav full')
    if t.count(lite_old) != 1:
        note('ABORT webdav lite trees anchor count=' + str(t.count(lite_old)))
        raise Abort('webdav lite')

    t2 = t.replace(full_old, full_new, 1).replace(lite_old, lite_new, 1)
    if balance(t2) != bal0:
        note('ABORT webdav balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        raise Abort('webdav balance')
    if full_new not in t2 or lite_new not in t2:
        note('ABORT webdav selfcheck')
        raise Abort('webdav selfcheck')
    p.write_text(t2, encoding='utf-8')
    note('WebDavSync OK: trees include scripts (full + lite)')


def patch_restorer():
    p = ROOT / RESTORER
    if not p.exists():
        note('ABORT missing BackupArchiveRestorer.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhBackupScripts265' in t:
        note('restorer already applied')
        return
    bal0 = balance(t)

    # 1. 分发链两处（内容相同，replace_all）
    dist_old = 'safeName.startsWith("${FileFolders.TOOL_OUTPUTS}/") -> resolveStagedFile(staging, safeName)'
    dist_new = (dist_old + NL +
                '                            safeName.startsWith("scripts/") -> resolveStagedFile(staging, safeName) // rhBackupScripts265')
    n = t.count(dist_old)
    if n != 2:
        note('ABORT restorer dist anchor count=' + str(n) + ' (expected 2)')
        raise Abort('restorer dist')

    # 2. rootAliases
    alias_old = '"tool-outputs" to FileFolders.TOOL_OUTPUTS,'
    alias_new = (alias_old + NL +
                 '            "scripts" to "scripts", // rhBackupScripts265' + NL +
                 '            "script" to "scripts", // rhBackupScripts265')
    if t.count(alias_old) != 1:
        note('ABORT restorer alias anchor count=' + str(t.count(alias_old)))
        raise Abort('restorer alias')

    # 3. 守卫集合子串
    guard_old = '"workspaces", "workspace"'
    guard_new = '"workspaces", "workspace", "scripts", "script"'
    if t.count(guard_old) != 1:
        note('ABORT restorer guard anchor count=' + str(t.count(guard_old)))
        raise Abort('restorer guard')

    t2 = t.replace(dist_old, dist_new).replace(alias_old, alias_new, 1).replace(guard_old, guard_new, 1)
    if balance(t2) != bal0:
        note('ABORT restorer balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        raise Abort('restorer balance')
    for need in ['"scripts" to "scripts"', '"script" to "scripts"',
                 '"workspaces", "workspace", "scripts", "script"',
                 'safeName.startsWith("scripts/")']:
        if need not in t2:
            note('ABORT restorer selfcheck missing ' + need)
            raise Abort('restorer selfcheck')
    if t2.count('safeName.startsWith("scripts/")') != 2:
        note('ABORT restorer dist count=' + str(t2.count('safeName.startsWith("scripts/")')) + ' (expected 2)')
        raise Abort('restorer dist count')
    p.write_text(t2, encoding='utf-8')
    note('BackupArchiveRestorer OK: scripts entries resolve back to filesDir/scripts')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch265 diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch265 diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    for name, fn in [('1 WebDavSync trees', patch_webdav), ('2 BackupArchiveRestorer', patch_restorer)]:
        try:
            fn()
            note(name + ' DONE')
        except Abort as e:
            note(name + ' ABORTED (no file written): ' + str(e))
        except Exception as e:
            note(name + ' EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
        print('::error::batch265 part: ' + name)
        sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch265 ' + str(line)[:800])
    print('::error::batch265 END lines=' + str(len(report)))


main()