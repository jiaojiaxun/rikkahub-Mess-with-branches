#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch216: 备份合并"全部用备份 / 全部留本地"一键按钮（warn-only）

需求: 用户反馈合并时"其他都是原版、助手只改了一部分"——设置条目/标量偏好的保守默认值
      (MODIFIED→保留本地、标量→默认不采用)让备份内容默认不进来, 逐项翻太麻烦。

修法(三层联动, 锚点全部选在链脚本注入行, 各自独立幂等 marker rhMergeBulk):
  1. BackupVM.kt: +mergeAllUseBackup/mergeAllKeepLocal 两方法(锚 confirmMerge);
     补 ConversationMergeRelation/SettingsItemKind 两个 import(锚 batch156 注入的 import)
  2. MergeConfirmDialog.kt(batch157 生成): 签名 +onApplyAllBackup/onKeepAllLocal(锚 onConfirm 参数);
     底部操作行上方加一行两个 TextButton(锚操作行的 Arrangement.spacedBy 特征行, 向上找 Row()
  3. BackupPage.kt: 调用点补两个实参(锚 onConfirm 实参)

效果: 差异确认弹窗底部新增"全部保留本地"/"全部用备份", 一键整体偏向, 之后仍可逐项微调再合并。

五查:
 1. import: VM 需补 2 个(ensure-import, 缺才加); dialog/page 复用已有 import 零新增
 2. 同文件冲突: BackupVM/MergeConfirmDialog/BackupPage 仅被 batch150-159 碰过, 锚点互不重叠
 3. 作用域: VM 方法与 confirmMerge 同级(类体内); dialog 按钮在操作行上方(同 composable 域)
 4. 括号配对: 每文件写入前断言 balance 不变
 5. 函数签名: VM 纯新增方法; dialog 新参数带默认值(旧调用点不受影响); page 补的实参与之对应
Python 三查: 引号变量构造 / NL 手写 concat / 无 f-string / 反斜杠只出现在 r 原始串。
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
BATCH = 'batch216'
MARK = 'rhMergeBulk'

VM = 'app/src/main/java/me/rerere/rikkahub/ui/pages/backup/BackupVM.kt'
DLG = 'app/src/main/java/me/rerere/rikkahub/ui/pages/backup/MergeConfirmDialog.kt'
PAGE = 'app/src/main/java/me/rerere/rikkahub/ui/pages/backup/BackupPage.kt'

applied = []
skipped = []


def ok(tag):
    if tag not in applied:
        applied.append(tag)


def skip(tag, why):
    skipped.append(tag + '<' + str(why)[:80] + '>')


def safe(name, fn, default=None):
    try:
        return fn()
    except Exception as exc:
        skip(name, 'crash:' + str(exc)[:60])
        return default


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


def concat(lines):
    t = ''
    for i, ln in enumerate(lines):
        if i > 0:
            t += NL
        t += ln
    return t


def joinlist(items):
    t = ''
    for i, s in enumerate(items):
        if i > 0:
            t += ','
        t += s
    return t


def read(path):
    p = ROOT / path
    if not p.exists():
        return None
    try:
        return p.read_text(encoding='utf-8')
    except Exception:
        return None


def write(path, text):
    p = ROOT / path
    if not p.parent.exists():
        p.parent.mkdir(parents=True)
    p.write_text(text, encoding='utf-8')


def ensure_import(lines, want, anchor):
    '''缺才加 import(行级 strip 全等), 插在 anchor import 行后。'''
    for ln in lines:
        if ln.strip() == want:
            return True
    hi = -1
    for i, ln in enumerate(lines):
        if ln.strip() == anchor:
            hi = i
            break
    if hi < 0:
        return False
    lines.insert(hi + 1, want)
    return True


# ============================================================
# VM 新方法（bulk 决策）
# ============================================================
VM_METHODS = r'''
    /** [batch216] 一键全部采用备份（对话+设置条目+标量偏好都用备份侧），之后仍可逐项微调。 */
    fun mergeAllUseBackup() {
        val state = mergeUiState.value as? MergeUiState.AwaitingDecision ?: return
        val plan = state.plan
        val convs = plan.conversations.map { item ->
            val d = when (item.relation) {
                ConversationMergeRelation.NEW -> ConversationMergeDecision.IMPORT
                ConversationMergeRelation.SAME -> ConversationMergeDecision.KEEP_LOCAL
                else -> ConversationMergeDecision.USE_BACKUP
            }
            item.copy(decision = d)
        }
        val settings = plan.settings?.let { s ->
            s.copy(
                items = s.items.map { item ->
                    item.copy(decision = when (item.kind) {
                        SettingsItemKind.ADDED_IN_BACKUP -> SettingsItemDecision.IMPORT
                        SettingsItemKind.DELETED_LOCALLY -> SettingsItemDecision.IMPORT
                        SettingsItemKind.REMOVED_IN_BACKUP -> SettingsItemDecision.DELETE
                        SettingsItemKind.MODIFIED -> SettingsItemDecision.USE_BACKUP
                    })
                },
                scalarFields = s.scalarFields.map { it.copy(adoptBackup = true) },
            )
        }
        mergeUiState.value = state.copy(plan = plan.copy(conversations = convs, settings = settings))
    }

    /** [batch216] 一键全部保留本地（重置为扫描时的默认决策）。 */
    fun mergeAllKeepLocal() {
        val state = mergeUiState.value as? MergeUiState.AwaitingDecision ?: return
        val plan = state.plan
        val convs = plan.conversations.map { it.copy(decision = it.defaultDecision) }
        val settings = plan.settings?.let { s ->
            s.copy(
                items = s.items.map { it.copy(decision = it.defaultDecision) },
                scalarFields = s.scalarFields.map { it.copy(adoptBackup = false) },
            )
        }
        mergeUiState.value = state.copy(plan = plan.copy(conversations = convs, settings = settings))
    }
'''


# ============================================================
# 阶段 1: BackupVM.kt
# ============================================================
def phase_vm():
    src = read(VM)
    if src is None:
        skip('vm', 'missing')
        return
    if MARK in src:
        ok('vm-exists')
        return
    lines = src.split(NL)
    bal0 = balance(src)

    imp_anchor = 'import me.rerere.rikkahub.data.sync.merge.ConversationMergeDecision'
    ok_imp = True
    for want in (
        'import me.rerere.rikkahub.data.sync.merge.ConversationMergeRelation',
        'import me.rerere.rikkahub.data.sync.merge.SettingsItemKind',
    ):
        if not ensure_import(lines, want, imp_anchor):
            ok_imp = False
    if not ok_imp:
        skip('vm', 'import-anchor')
        return

    hits = [i for i, ln in enumerate(lines) if ln.strip() == 'fun confirmMerge() {']
    if len(hits) != 1:
        skip('vm', 'anchor=' + str(len(hits)))
        return
    ci = hits[0]
    lines[ci:ci] = VM_METHODS.rstrip(NL).split(NL)

    out = concat(lines)
    if balance(out) != bal0:
        skip('vm', 'balance')
        return
    if 'fun mergeAllUseBackup()' not in out or 'fun mergeAllKeepLocal()' not in out:
        skip('vm', 'selfcheck')
        return
    write(VM, out)
    ok('vm')


# ============================================================
# 阶段 2: MergeConfirmDialog.kt（batch157 生成的 CI 文件）
# ============================================================
def phase_dialog():
    src = read(DLG)
    if src is None:
        skip('dialog', 'missing')
        return
    if MARK in src:
        ok('dialog-exists')
        return
    lines = src.split(NL)
    bal0 = balance(src)

    # 2a. 签名加两个回调(锚 onConfirm 参数行)
    hits = [i for i, ln in enumerate(lines) if ln.strip() == 'onConfirm: () -> Unit,']
    if len(hits) != 1:
        skip('dialog', 'sig-anchor=' + str(len(hits)))
        return
    si = hits[0]
    d = ind(lines[si])
    lines[si:si] = [
        d + 'onApplyAllBackup: () -> Unit = {}, // ' + MARK,
        d + 'onKeepAllLocal: () -> Unit = {}, // ' + MARK,
    ]

    # 2b. 底部操作行上方加一行两个按钮(锚操作行的 spacedBy 特征行, 向上找 Row()
    hits = [i for i, ln in enumerate(lines) if 'Arrangement.spacedBy(12.dp, Alignment.End)' in ln]
    if len(hits) != 1:
        skip('dialog', 'btnrow-anchor=' + str(len(hits)))
        return
    ai = hits[0]
    row_start = -1
    for j in range(ai, max(ai - 8, -1), -1):
        if lines[j].strip() == 'Row(':
            row_start = j
            break
    if row_start < 0:
        skip('dialog', 'btnrow-start')
        return
    d = ind(lines[row_start])
    lines[row_start:row_start] = [
        d + '// ' + MARK + ': 一键全部采用备份 / 全部保留本地',
        d + 'Row(',
        d + '    modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp),',
        d + '    horizontalArrangement = Arrangement.spacedBy(12.dp),',
        d + ') {',
        d + '    TextButton(onClick = onKeepAllLocal) { Text("全部保留本地") }',
        d + '    TextButton(onClick = onApplyAllBackup) { Text("全部用备份") }',
        d + '}',
    ]

    out = concat(lines)
    if balance(out) != bal0:
        skip('dialog', 'balance')
        return
    if 'onApplyAllBackup: () -> Unit' not in out or 'onApplyAllBackup) { Text("全部用备份") }' not in out:
        skip('dialog', 'selfcheck')
        return
    write(DLG, out)
    ok('dialog')


# ============================================================
# 阶段 3: BackupPage.kt（调用点补实参）
# ============================================================
def phase_page():
    src = read(PAGE)
    if src is None:
        skip('page', 'missing')
        return
    if MARK in src:
        ok('page-exists')
        return
    lines = src.split(NL)
    bal0 = balance(src)

    hits = [i for i, ln in enumerate(lines) if 'onConfirm = { vm.confirmMerge() },' in ln]
    if len(hits) != 1:
        skip('page', 'anchor=' + str(len(hits)))
        return
    ci = hits[0]
    d = ind(lines[ci])
    lines[ci:ci] = [
        d + 'onApplyAllBackup = vm::mergeAllUseBackup, // ' + MARK,
        d + 'onKeepAllLocal = vm::mergeAllKeepLocal, // ' + MARK,
    ]

    out = concat(lines)
    if balance(out) != bal0:
        skip('page', 'balance')
        return
    if 'onApplyAllBackup = vm::mergeAllUseBackup' not in out:
        skip('page', 'selfcheck')
        return
    write(PAGE, out)
    ok('page')


def main():
    safe('vm', phase_vm)
    safe('dialog', phase_dialog)
    safe('page', phase_page)
    print('::warning::' + BATCH + ' applied=[' + joinlist(applied) + '] skipped=[' + joinlist(skipped) + ']')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('::warning::' + BATCH + ' crashed: ' + str(exc)[:400])
    sys.exit(0)