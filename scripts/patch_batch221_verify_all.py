#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch221: 全量交付验证（只读不改，走 ::error 通道）

背景: run410 发现 GitHub 每个步骤最多挂 10 条 warning annotation, patch 步骤已满
      (149v2/133/168/214/215x2/216/217/218/219 共 10 条) → batch220 的汇报被丢弃。
      本脚本改用 ::error 通道(当前为空)——它不是错误, 只是借空通道露出验证结果。
      纯验证: 不写文件, 不改代码, exit 0。

清点范围: 213 自定义工具全链 / 215 rootfs+加载提示 / 216 合并按钮三层 / 217 榨干断链 /
          218 rootfs 真修 / 219+220 proot 二进制 / 220 榨干续跑 / native 扫描。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
BATCH = 'batch221'

CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'
LT = 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt'
AP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/assistant/detail/AssistantLocalToolPage.kt'
RA = 'app/src/main/java/me/rerere/rikkahub/RouteActivity.kt'
SP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPage.kt'
STORE = 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/custom/CustomToolStore.kt'
TOOLS = 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/custom/CustomToolTools.kt'
PAGE = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingCustomToolsPage.kt'
BP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/backup/BackupPage.kt'
VM = 'app/src/main/java/me/rerere/rikkahub/ui/pages/backup/BackupVM.kt'
DLG = 'app/src/main/java/me/rerere/rikkahub/ui/pages/backup/MergeConfirmDialog.kt'
RP = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ReasoningPicker.kt'
RI = 'workspace/src/main/java/me/rerere/workspace/RootfsInstaller.kt'

PROOT_ARM = 'workspace/src/main/jniLibs/arm64-v8a/'
PROOT_X64 = 'workspace/src/main/jniLibs/x86_64/'

NATIVE = (
    ('bg', 'workspace/src/main/java/me/rerere/workspace/WorkspaceBackgroundProcesses.kt'),
    ('fs', 'workspace/src/main/java/me/rerere/workspace/WorkspaceFileSystem.kt'),
    ('ws', 'workspace/src/main/java/me/rerere/workspace/Workspace.kt'),
    ('sr', 'workspace/src/main/java/me/rerere/workspace/WorkspaceShellRunner.kt'),
)

TEXT_CHECKS = (
    (CS, 'rhSqueezeWire', 'squeeze220'),
    (LT, 'data object CustomTools : LocalToolOption()', 'enum213'),
    (LT, 'customTools(context, jsSkillRunner)', 'gate213'),
    (AP, 'rhCustomToolsRow', 'row213'),
    (RA, 'data object SettingCustomTools : Screen', 'sval213'),
    (RA, 'entry<Screen.SettingCustomTools>', 'entry213'),
    (SP, 'Screen.SettingCustomTools', 'srow213'),
    (STORE, 'class CustomToolStore', 'store213'),
    (TOOLS, 'fun customTools(', 'tools213'),
    (PAGE, 'fun SettingCustomToolsPage()', 'page213'),
    (BP, 'rhMergeLoadingTip', 'loading215'),
    (BP, 'rhMergeBulk', 'bulk216page'),
    (VM, 'fun mergeAllUseBackup()', 'bulk216vm'),
    (DLG, 'onApplyAllBackup', 'bulk216dlg'),
    (RP, 'rhBatch217Wire', 'wire217'),
    (RI, 'isBlankRootEntry', 'rootfs215'),
    (RI, 'rhRootfsSkip218', 'rootfs218'),
)

SIZE_CHECKS = (
    (PROOT_ARM + 'libproot_exec.so', 233392, 'proot-arm-exec'),
    (PROOT_ARM + 'libproot_loader.so', 18136, 'proot-arm-loader'),
    (PROOT_X64 + 'libproot_exec.so', 246408, 'proot-x64-exec'),
    (PROOT_X64 + 'libproot_loader.so', 18352, 'proot-x64-loader'),
)


def read(path):
    p = ROOT / path
    if not p.exists():
        return None
    try:
        return p.read_text(encoding='utf-8')
    except Exception:
        return None


def main():
    parts = []
    for path, needle, label in TEXT_CHECKS:
        src = read(path)
        if src is None:
            parts.append(label + '=NOFILE')
        else:
            parts.append(label + ('=ok' if needle in src else '=MISS'))
    for path, size, label in SIZE_CHECKS:
        p = ROOT / path
        if not p.exists():
            parts.append(label + '=NOFILE')
        else:
            try:
                actual = p.stat().st_size
                parts.append(label + ('=ok' if actual == size else '=size' + str(actual)))
            except Exception:
                parts.append(label + '=err')
    for label, path in NATIVE:
        src = read(path)
        if src is None:
            parts.append('nat-' + label + '=miss')
        else:
            n = src.count('loadLibrary') + src.count('System.load') + src.count('externalNativeBuild')
            parts.append('nat-' + label + '=' + str(n))
    line = BATCH + '-VERIFY ' + ' '.join(parts)
    print('::error::' + line[:1900])
    print(line[:1900])


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('::error::' + BATCH + ' crashed: ' + str(exc)[:300])
    sys.exit(0)