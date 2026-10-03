#!/usr/bin/env python3
"""batch37 v2: 定时任务设置页接线（修复 #120 锚点错误）

#120 失败根因（又犯了铁律 1：猜锚点没读源码）：
  RouteActivity 的 entry 用的是**全限定名**
    entry<Screen.SettingToolApprovals> {
        me.rerere.rikkahub.ui.pages.setting.SettingToolApprovalsPage()
    }
  而我猜的是裸名 SettingToolApprovalsPage() → 锚点找不到。

v2 修正：锚点改用真实源码（含三处换行 + 全限定名），新 entry body 也用
全限定名，避免依赖 import。

四处改动：
1. Screen sealed interface 加 SettingScheduledJobs（锚点：Stats）
2. entryProvider 加 entry（锚点：SettingToolApprovals 真实块）
3. import 补 SettingScheduledJobsPage（搭在 SettingPage import 后面，兜底正则）
4. SettingPage 高级服务组加入口（锚点：SettingFiles item）

铁律：不用 f-string；含 Kotlin 双引号块用 Python 单引号；幂等标记 rhScheduledJobs
"""
from pathlib import Path
import re

ROOT = Path.cwd()
MARK = "rhScheduledJobs"


def fail(path, msg):
    print('::error file=' + path + '::batch37 ' + msg[:1400])
    raise SystemExit(1)


# --- 1 & 2 & 3. RouteActivity.kt ---
P_ROUTE = "app/src/main/java/me/rerere/rikkahub/RouteActivity.kt"
t = (ROOT / P_ROUTE).read_text(encoding="utf-8")

if MARK in t:
    print("batch37: RouteActivity already wired")
else:
    # 1. Screen 定义（排在 Stats 后面）
    ANCHOR_SCREEN = (
        '    @Serializable\n'
        '    data object Stats : Screen\n'
    )
    idx = t.find(ANCHOR_SCREEN)
    if idx < 0:
        fail(P_ROUTE, "Screen.Stats anchor not found")
    new_screen = ANCHOR_SCREEN + (
        '\n'
        '    /** rhScheduledJobs */\n'
        '    @Serializable\n'
        '    data object SettingScheduledJobs : Screen\n'
    )
    t = t[:idx] + new_screen + t[idx + len(ANCHOR_SCREEN):]

    # 2. entryProvider（真实源码：全限定名）
    ANCHOR_ENTRY = (
        '                            entry<Screen.SettingToolApprovals> {\n'
        '                                me.rerere.rikkahub.ui.pages.setting.SettingToolApprovalsPage()\n'
        '                            }\n'
    )
    eidx = t.find(ANCHOR_ENTRY)
    if eidx < 0:
        fail(P_ROUTE, "entryProvider SettingToolApprovals anchor not found (v2)")
    new_entry = ANCHOR_ENTRY + (
        '\n'
        '                            /* rhScheduledJobs */\n'
        '                            entry<Screen.SettingScheduledJobs> {\n'
        '                                me.rerere.rikkahub.ui.pages.setting.SettingScheduledJobsPage()\n'
        '                            }\n'
    )
    t = t[:eidx] + new_entry + t[eidx + len(ANCHOR_ENTRY):]

    # 3. import（兜底：找任意 setting 包 import 插入）
    if 'import me.rerere.rikkahub.ui.pages.setting.SettingScheduledJobsPage' not in t:
        anchor_import = 'import me.rerere.rikkahub.ui.pages.setting.SettingPage\n'
        if anchor_import in t:
            t = t.replace(
                anchor_import,
                anchor_import + 'import me.rerere.rikkahub.ui.pages.setting.SettingScheduledJobsPage\n',
                1,
            )
        else:
            m = re.search(r'import me\.rerere\.rikkahub\.ui\.pages\.setting\.[A-Za-z0-9_]+\n', t)
            if not m:
                fail(P_ROUTE, "no setting import anchor found")
            t = (t[:m.start()]
                 + 'import me.rerere.rikkahub.ui.pages.setting.SettingScheduledJobsPage\n'
                 + t[m.start():])

    (ROOT / P_ROUTE).write_text(t, encoding="utf-8")
    print("batch37: RouteActivity wired (Screen + entry + import)")

# --- 4. SettingPage.kt 加入口 ---
P_SETTING = "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPage.kt"
ts = (ROOT / P_SETTING).read_text(encoding="utf-8")

if MARK in ts:
    print("batch37: SettingPage already has entry")
else:
    ANCHOR_FILES = (
        '                    item(\n'
        '                        onClick = { navController.navigate(Screen.SettingFiles) },\n'
        '                        leadingContent = { Icon(HugeIcons.ImageUpload, null) },\n'
        '                        supportingContent = { Text(stringResource(R.string.setting_page_workspace_files_desc)) },\n'
        '                        headlineContent = { Text(stringResource(R.string.setting_page_workspace_files)) },\n'
        '                    )\n'
    )
    fidx = ts.find(ANCHOR_FILES)
    if fidx < 0:
        fail(P_SETTING, "SettingFiles item anchor not found")
    new_item = ANCHOR_FILES + (
        '                    /* rhScheduledJobs */\n'
        '                    item(\n'
        '                        onClick = { navController.navigate(Screen.SettingScheduledJobs) },\n'
        '                        leadingContent = { Icon(HugeIcons.Clock02, null) },\n'
        '                        supportingContent = { Text("查看、开关、删除 AI 创建的定时任务") },\n'
        '                        headlineContent = { Text("定时任务") },\n'
        '                    )\n'
    )
    ts = ts[:fidx] + new_item + ts[fidx + len(ANCHOR_FILES):]
    (ROOT / P_SETTING).write_text(ts, encoding="utf-8")
    print("batch37: SettingPage entry added")

print("batch37: OK")
