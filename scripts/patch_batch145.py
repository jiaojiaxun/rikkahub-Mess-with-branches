#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch145: 工作区详情页加 Rootfs 安装卡片（WorkspaceInstallCard）

用户需求: 装机后 workspace_shell 能用,但没有 UI 安装入口(rootfs 装不上)。
方案: 新文件 WorkspaceInstallCard.kt + WorkspaceInstallVM.kt(已随仓库推送),
在 WorkspaceDetailPage 的基础信息页插入一行调用 + ViewModelModule 注册 VM。

改动(两文件锚点插入):
1. WorkspaceDetailPage.kt: 在 WorkspaceToolApprovalCard 的 item 之前插入
   WorkspaceInstallCard(workspace = workspace) 的 item(同包,无需 import)。
2. ViewModelModule.kt: 在 viewModel<WorkspaceDetailVM> { 之前插入
   viewModel<WorkspaceInstallVM> { params -> ... } 注册(同包,无需 import)。

五查:
1. import 清单: 两文件均同包(extensions.workspace),无需 import
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

# ---- 2. ViewModelModule.kt: 注册 WorkspaceInstallVM ----
t = (ROOT / VM).read_text(encoding='utf-8')
if 'WorkspaceInstallVM' in t:
    print('batch145: ViewModelModule already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)
    # 锚点: viewModel<WorkspaceDetailVM> { 行
    anchor_hits = [i for i, ln in enumerate(lines) if ln.strip() == 'viewModel<WorkspaceDetailVM> {']
    if len(anchor_hits) != 1:
        fail('ViewModelModule anchor count=' + str(len(anchor_hits)))
    idx = anchor_hits[0]
    indent = lines[idx][:len(lines[idx]) - len(lines[idx].lstrip())]
    new_block = [
        indent + 'viewModel<WorkspaceInstallVM> { params ->',
        indent + '    WorkspaceInstallVM(',
        indent + '        workspaceId = params.get(),',
        indent + '        repository = get(),',
        indent + '    )',
        indent + '}',
        '',
    ]
    for offset, seg in enumerate(new_block):
        lines.insert(idx + offset, seg)
    out = NL.join(lines)
    if 'WorkspaceInstallVM' not in out:
        fail('ViewModelModule selfcheck failed')
    if balance(out) != bal0:
        fail('ViewModelModule balance changed')
    (ROOT / VM).write_text(out, encoding='utf-8')
    print('::notice::batch145 ViewModelModule OK')

print('batch145: ALL OK')
