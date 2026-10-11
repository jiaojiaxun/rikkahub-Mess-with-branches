#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch145 v2: 工作区详情页加 Rootfs 安装卡片 — 补 ViewModelModule 的 import

v2 修复: v1 往 ViewModelModule 插了 viewModel<WorkspaceInstallVM> { ... } 注册块,
但 WorkspaceInstallVM 在 ui.pages.extensions.workspace 包, ViewModelModule 在 di 包
——不同包需要 import, v1 漏了 → 编译 Unresolved reference 'WorkspaceInstallVM'。
v2 修法: 在 ViewModelModule 里先加 import(锚点: WorkspaceDetailVM 的 import 行后),
再插注册块(锚点: viewModel<WorkspaceDetailVM> { 行前)。其余不变。

用户需求: 装机后 workspace_shell 能用,但没有 UI 安装入口(rootfs 装不上)。
方案: 新文件 WorkspaceInstallCard.kt + WorkspaceInstallVM.kt(已随仓库推送),
在 WorkspaceDetailPage 的基础信息页插入一行调用 + ViewModelModule 注册 VM + import。

改动(两文件锚点插入):
1. WorkspaceDetailPage.kt: 在 WorkspaceToolApprovalCard 的 item 之前插入
   WorkspaceInstallCard(workspace = workspace) 的 item(同包 extensions.workspace,无需 import)。
2. ViewModelModule.kt: 先加 import WorkspaceInstallVM,再在 viewModel<WorkspaceDetailVM> {
   前插 viewModel<WorkspaceInstallVM> { params -> ... } 注册块。

五查:
1. import 清单: ViewModelModule 需新增 WorkspaceInstallVM import(不同包,必须);
   DetailPage 侧同包 extensions.workspace 无需 import ✓
2. 同文件冲突: WorkspaceDetailPage.kt / ViewModelModule.kt 无在链 patch 触碰
3. 作用域: WorkspaceInstallCard 调用在 WorkspaceBasicPage 的 LazyColumn item 内,
   workspace 参数可见; WorkspaceInstallVM 注册在 viewModelModule 顶层
4. 括号配对: 插入行自平衡(item { ... } / viewModel { ... } 块),全文件 balance 前后一致
5. 函数签名: 不改签名,新增调用走已定义 composable/VM

Python 三查: 引号用 Q=chr(34) 构造;NL 手写 concat;helper 先定义;失败显式 exit(1)+::error
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhWsInstallCard'
DP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/WorkspaceDetailPage.kt'
VM = 'app/src/main/java/me/rerere/rikkahub/di/ViewModelModule.kt'


def fail(msg):
    print('::error file=' + DP + '/' + VM + '::batch145 ' + str(msg)[:1400])
    sys.stdout.flush()
    sys.exit(1)


def balance(text):
    return text.count('(') - text.count(')') + (text.count('{') - text.count('}'))


# ---- 1. WorkspaceDetailPage.kt: 插入 WorkspaceInstallCard item ----
t = (ROOT / DP).read_text(encoding='utf-8')
if MARK in t:
    print('batch145: DetailPage already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)
    # 锚点: item { + WorkspaceToolApprovalCard( 组合(两行)
    anchor_hits = []
    for i in range(len(lines) - 1):
        if lines[i].strip() == 'item {' and 'WorkspaceToolApprovalCard(' in lines[i + 1]:
            anchor_hits.append(i)
    if len(anchor_hits) != 1:
        fail('DetailPage anchor count=' + str(len(anchor_hits)))
    idx = anchor_hits[0]
    indent = lines[idx][:len(lines[idx]) - len(lines[idx].lstrip())]
    # 在 item { 之前插入新 item 块
    new_block = [
        indent + 'item {',
        indent + '    // ' + MARK + ': Rootfs 安装卡片(Linux 环境)',
        indent + '    WorkspaceInstallCard(workspace = workspace)',
        indent + '}',
        '',
    ]
    for offset, seg in enumerate(new_block):
        lines.insert(idx + offset, seg)
    out = NL.join(lines)
    if MARK not in out or 'WorkspaceInstallCard(workspace = workspace)' not in out:
        fail('DetailPage selfcheck failed')
    if balance(out) != bal0:
        fail('DetailPage balance changed')
    (ROOT / DP).write_text(out, encoding='utf-8')
    print('::notice::batch145 DetailPage OK')

# ---- 2. ViewModelModule.kt: 加 import + 注册 WorkspaceInstallVM ----
t = (ROOT / VM).read_text(encoding='utf-8')
if 'WorkspaceInstallVM' in t:
    print('batch145: ViewModelModule already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)
    # 2a. 加 import(锚点: import ...WorkspaceDetailVM 行后)
    imp_anchor = 'import me.rerere.rikkahub.ui.pages.extensions.workspace.WorkspaceDetailVM'
    imp_hits = [i for i, ln in enumerate(lines) if ln.strip() == imp_anchor]
    if len(imp_hits) != 1:
        fail('ViewModelModule import anchor count=' + str(len(imp_hits)))
    imp_idx = imp_hits[0]
    lines.insert(imp_idx + 1, 'import me.rerere.rikkahub.ui.pages.extensions.workspace.WorkspaceInstallVM')
    # 2b. 加注册块(锚点: viewModel<WorkspaceDetailVM> { 行前)
    vm_hits = [i for i, ln in enumerate(lines) if ln.strip() == 'viewModel<WorkspaceDetailVM> {']
    if len(vm_hits) != 1:
        fail('ViewModelModule viewModel anchor count=' + str(len(vm_hits)))
    vm_idx = vm_hits[0]
    vm_indent = lines[vm_idx][:len(lines[vm_idx]) - len(lines[vm_idx].lstrip())]
    new_block = [
        vm_indent + 'viewModel<WorkspaceInstallVM> { params ->',
        vm_indent + '    WorkspaceInstallVM(',
        vm_indent + '        workspaceId = params.get(),',
        vm_indent + '        repository = get(),',
        vm_indent + '    )',
        vm_indent + '}',
        '',
    ]
    for offset, seg in enumerate(new_block):
        lines.insert(vm_idx + offset, seg)
    out = NL.join(lines)
    if 'import me.rerere.rikkahub.ui.pages.extensions.workspace.WorkspaceInstallVM' not in out:
        fail('ViewModelModule import selfcheck failed')
    if 'viewModel<WorkspaceInstallVM>' not in out:
        fail('ViewModelModule viewModel selfcheck failed')
    if balance(out) != bal0:
        fail('ViewModelModule balance changed')
    (ROOT / VM).write_text(out, encoding='utf-8')
    print('::notice::batch145 ViewModelModule OK (import + register)')

print('batch145 v2: ALL OK')
