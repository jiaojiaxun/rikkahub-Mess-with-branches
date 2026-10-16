#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch214: batch213 自定义工具接线验证 + 管理页收集器加固

1) 验证: 检查 batch213 的各 marker 是否真正落到源码里(枚举/注册块/开关行/Screen/entry/
   设置入口/搜索条目/strings 中英/三个新文件), 汇总成一行 ::warning —— 匿名只能读
   annotation, 所以必须用正确的双冒号前缀(batch213 自己的汇总行写成单冒号, 读不到)。
2) 加固: SettingCustomToolsPage.kt 的 collectAsStateWithLifecycle() 无参调用改为
   collectAsStateWithLifecycle(initialValue = emptyList()) —— 对齐同目录已编译绿的
   SettingScheduledJobsPage 范式, 规避 StateFlow 重载在部分 lifecycle 版本缺失的风险。

warn-only: 任何失败只 ::warning, 不阻塞构建, 末尾正常退出。幂等。
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
BATCH = 'batch214'

PAGE = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingCustomToolsPage.kt'
OLD_CALL = 'val tools by store.toolsFlow.collectAsStateWithLifecycle()'
NEW_CALL = 'val tools by store.toolsFlow.collectAsStateWithLifecycle(initialValue = emptyList())'
FIX_MARK = 'rhCustomToolsCollectFix'

CHECKS = (
    ('store', 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/custom/CustomToolStore.kt', 'class CustomToolStore'),
    ('tools', 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/custom/CustomToolTools.kt', 'fun customTools('),
    ('page', 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingCustomToolsPage.kt', 'fun SettingCustomToolsPage()'),
    ('enum', 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt', 'data object CustomTools : LocalToolOption()'),
    ('gate', 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt', 'customTools(context, jsSkillRunner)'),
    ('row', 'app/src/main/java/me/rerere/rikkahub/ui/pages/assistant/detail/AssistantLocalToolPage.kt', 'rhCustomToolsRow'),
    ('sval', 'app/src/main/java/me/rerere/rikkahub/RouteActivity.kt', 'data object SettingCustomTools : Screen'),
    ('entry', 'app/src/main/java/me/rerere/rikkahub/RouteActivity.kt', 'entry<Screen.SettingCustomTools>'),
    ('srow', 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPage.kt', 'Screen.SettingCustomTools'),
    ('desc', 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPage.kt', 'AI 自定义工具'),
    ('search', 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingsSearchIndex.kt', 'route = Screen.SettingCustomTools'),
    ('str', 'app/src/main/res/values/strings.xml', 'setting_page_custom_tools'),
    ('strzh', 'app/src/main/res/values-zh/strings.xml', 'setting_page_custom_tools'),
)


def apply_collect_fix():
    try:
        p = ROOT / PAGE
        if not p.exists():
            return 'fix=no-page'
        src = p.read_text(encoding='utf-8')
        if FIX_MARK in src:
            return 'fix=already'
        if OLD_CALL not in src:
            return 'fix=no-anchor'
        out = src.replace(OLD_CALL, NEW_CALL + ' // ' + FIX_MARK, 1)
        if (src.count('(') - src.count(')')) != (out.count('(') - out.count(')')):
            return 'fix=balance'
        p.write_text(out, encoding='utf-8')
        return 'fix=applied'
    except Exception as exc:
        return 'fix=crash:' + str(exc)[:40]


def main():
    fix_note = apply_collect_fix()
    parts = []
    for name, path, needle in CHECKS:
        try:
            f = ROOT / path
            if not f.exists():
                parts.append(name + '=missing-file')
                continue
            txt = f.read_text(encoding='utf-8')
            parts.append(name + ('=ok' if needle in txt else '=MISS'))
        except Exception as exc:
            parts.append(name + '=err')
    line = BATCH + ' ' + fix_note + ' ' + ' '.join(parts)
    print('::warning::' + line[:1400])


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('::warning::' + BATCH + ' crashed: ' + str(exc)[:400])
    sys.exit(0)