#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch252: 工作区 shell 全线失效修复（/bin/bash 硬编码 -> 按 rootfs 选 shell）+ 记忆导入协调器取证

【T-W1 根因 —— 已实读 ProotShellRunner.kt 全文确认】
ProotShellRunner.buildCommand 末尾硬编码:
    command += listOf("/usr/bin/env", "-i", ... , "/bin/bash", "-l", "-c",
        "cd -- \\"\\$1\\" && eval \\"\\$2\\"", "rikkahub", context.prootCwd(), context.command)
而同一文件里的可用性检查只认 /bin/sh:
    private fun File.hasUsableRootfs(): Boolean = isDirectory && File(this, "bin/sh").isFile
=> 默认/推荐的 Alpine minirootfs 只有 busybox（/bin/sh -> busybox，无 bash），
   于是 shell 可用性检查通过、真正执行时却 exec /bin/bash 不存在 => 127，
   workspace_shell / write_file / edit_file / create_folder / run_background 全线失效
   （read_file / read_folder 走 Java IO，不受影响）。
修法: 新增 pickRootfsShell(linuxDir) —— File(linuxDir,"bin/bash") 存在用 /bin/bash，
      否则回退 /bin/sh；替换那行硬编码。
      busybox ash 支持 -l 与 -c 的位置参数，模板 cd -- "$1" && eval "$2" 无 bash 语法依赖，
      回退是安全的；有 bash 的旧环境（如 Ubuntu rootfs）行为完全不变。

【T-M4 重要更正 —— 上一批的 NULL 假设被证伪】
上一批怀疑 Migration_36_37 没写默认值导致旧记录 conversation_id 为 NULL、与 `= ''` 匹配不上。
本批实读 AppDatabase.kt 末尾:
    class Migration_36_37 : Migration(36, 37) {
        override fun migrate(db: SupportSQLiteDatabase) {
            db.execSQL("ALTER TABLE memoryentity ADD COLUMN conversation_id TEXT NOT NULL DEFAULT ''")
            db.execSQL("ALTER TABLE conversationentity ADD COLUMN config TEXT NOT NULL DEFAULT ''")
        }
    }
=> 带 NOT NULL DEFAULT ''，迁移后旧记录就是空串，NULL 假设不成立。**这条假设作废，不会据此改代码。**
新方向: 恢复走的是「完整 db 文件快照替换」（WebDavSync.createFullDatabaseSnapshot + copyTo），
   而 data/db 下存在一个 ImportedDatabaseReconciler.kt（20.5KB）——名字就是导入数据库协调器，
   很可能在里面做 assistant_id / conversation_id 的重映射。若它没有覆盖 memoryentity，
   恢复后记忆会挂在旧的 assistant_id 下，而记忆页按当前助手查询 => 一条都不显示。
本批 dump 它的全文关键行取证，下一批按实际逻辑修。

五查:
 1. import 清单: ProotShellRunner.kt 已 import java.io.File，pickRootfsShell 零新增 import
 2. 同文件冲突: ProotShellRunner.kt 在链上无其它批次改动（batch215/218/219/220 改的是
    RootfsInstaller / RootfsPatcher / jniLibs），本批锚点唯一
 3. 作用域: pickRootfsShell 为类内 private fun，调用点在 buildCommand(context, proot) 内，
    context.linuxDir 在作用域内
 4. 括号配对: `"/bin/bash"` -> `pickRootfsShell(context.linuxDir)` 各增 1 对括号；
    新函数块 (linuxDir: File) / File(...) / if (...) 共 3 对且自身配平 => 整文件 balance 不变（断言）
 5. 函数签名: buildCommand / execute / start / hasUsableRootfs 签名全部不变
Python 三查: Q/SQ 变量构造引号; NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 失败记录并继续
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
DIAG = 'ci_diag_batch252.txt'

PROOT = 'workspace/src/main/java/me/rerere/workspace/ProotShellRunner.kt'
RECONCILER = 'app/src/main/java/me/rerere/rikkahub/data/db/ImportedDatabaseReconciler.kt'

report = []


def note(msg):
    report.append(str(msg)[:900])


def balance(text):
    return (text.count('(') - text.count(')')
            + text.count('{') - text.count('}')
            + text.count('[') - text.count(']'))


def lines_to_text(lines):
    out = ''
    for idx, line in enumerate(lines):
        if idx > 0:
            out += NL
        out += line
    return out


def ind_of(line):
    s = line.lstrip()
    return line[:len(line) - len(s)]


def find_idx(lines, needle, label):
    hits = [i for i, ln in enumerate(lines) if ln.strip() == needle]
    if len(hits) == 0:
        note('ANCHOR-MISS ' + label + ' -> ' + repr(needle))
        raise RuntimeError('anchor miss ' + label)
    if len(hits) != 1:
        note('ANCHOR-DUP ' + label + ' count=' + str(len(hits)))
        raise RuntimeError('anchor dup ' + label)
    return hits[0]


def patch_shell():
    p = ROOT / PROOT
    if not p.exists():
        note('MISSING ProotShellRunner.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhShellFallback252' in t:
        note('proot already applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    # 1. 硬编码 /bin/bash -> pickRootfsShell(context.linuxDir)
    i = find_idx(lines, '"/bin/bash",', 'hardcoded bash')
    lines[i] = ind_of(lines[i]) + 'pickRootfsShell(context.linuxDir), // rhShellFallback252'

    # 2. 新增 pickRootfsShell（插在 hasUsableRootfs 之前）
    j = find_idx(lines, 'private fun File.hasUsableRootfs(): Boolean =', 'hasUsableRootfs')
    ji = ind_of(lines[j])
    fn = [
        ji + '/**',
        ji + ' * rhShellFallback252: 默认/推荐的 Alpine minirootfs 只有 busybox，没有 /bin/bash。',
        ji + ' * 之前这里硬编码 /bin/bash，导致 rootfs 检查（只认 bin/sh）通过、执行却 127 退出，',
        ji + ' * workspace_shell / write_file / edit_file / create_folder / run_background 全线失效。',
        ji + ' * busybox ash 支持 -l 与 -c 的位置参数，脚本模板无 bash 语法依赖，回退安全；',
        ji + ' * 有 bash 的环境（如 Ubuntu rootfs）行为完全不变。',
        ji + ' */',
        ji + 'private fun pickRootfsShell(linuxDir: File): String =',
        ji + '    if (File(linuxDir, "bin/bash").isFile) "/bin/bash" else "/bin/sh"',
        ji + '',
    ]
    lines = lines[:j] + fn + lines[j:]

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('proot balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        return
    for need in ['pickRootfsShell(context.linuxDir), // rhShellFallback252',
                 'private fun pickRootfsShell(linuxDir: File): String =',
                 'if (File(linuxDir, "bin/bash").isFile) "/bin/bash" else "/bin/sh"']:
        if need not in t2:
            note('proot selfcheck missing ' + need)
            return
    if '"' + '/bin/bash' + '"' + ',' + NL in t2:
        note('proot hardcoded bash still present')
        return
    p.write_text(t2, encoding='utf-8')
    note('proot OK: shell picked by rootfs content (bash -> fallback sh)')


def probe_reconciler():
    p = ROOT / RECONCILER
    if not p.exists():
        note('probe missing ImportedDatabaseReconciler.kt')
        return
    lines = p.read_text(encoding='utf-8').split(NL)
    note('reconciler lines=' + str(len(lines)))
    keys = ['memoryentity', 'MemoryEntity', 'assistant_id', 'assistantId', 'UPDATE ',
            'conversation_id', 'remap', 'Remap', 'reconcile', 'Reconcile', 'DELETE FROM', 'INSERT INTO']
    hits = []
    for i, ln in enumerate(lines):
        s = ln.strip()
        for k in keys:
            if k in s:
                hits.append('L' + str(i + 1) + ':' + s[:190])
                break
    note('reconciler hits=' + str(len(hits)))
    for h in hits[:60]:
        note('rec ' + h)


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch252 diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch252 diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    for name, fn in [
        ('1 rootfs shell fallback', patch_shell),
        ('2 imported-db reconciler probe', probe_reconciler),
    ]:
        try:
            fn()
            note(name + ' DONE')
        except Exception as e:
            note(name + ' EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
        print('::error::batch252 part: ' + name)
        sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch252 ' + str(line)[:800])
    print('::error::batch252 END lines=' + str(len(report)))


main()