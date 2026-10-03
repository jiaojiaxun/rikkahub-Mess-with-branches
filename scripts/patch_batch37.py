#!/usr/bin/env python3
"""batch37: 定时任务设置页接线

四处改动：
1. RouteActivity.kt Screen sealed interface 加 SettingScheduledJobs
2. RouteActivity.kt entryProvider 加 entry<Screen.SettingScheduledJobs>
3. RouteActivity.kt import SettingScheduledJobsPage
4. SettingPage.kt 高级服务 CardGroup 加“定时任务”入口

锚点（已用 API 读真实源码）：
  Screen 尾部：'    @Serializable\n    data object Stats : Screen\n\n}'\n
  entryProvider：entry<Screen.SettingToolApprovals> { ... }\n
  SettingPage：onClick = { navController.navigate(Screen.SettingFiles) } 那块

铁律：不用 f-string；含 Kotlin 双引号块用 Python 单引号；幂等标记 rhScheduledJobs
"""
from pathlib import Path

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

    # 2. entryProvider
    ANCHOR_ENTRY = (
        '                            entry<Screen.SettingToolApprovals> {\n'
        '                                SettingToolApprovalsPage()\n'
        '                            }\n'
    )
    eidx = t.find(ANCHOR_ENTRY)
    if eidx < 0:
        fail(P_ROUTE, "entryProvider SettingToolApprovals anchor not found")
    new_entry = ANCHOR_ENTRY + (
        '\n'
        '                            entry<Screen.SettingScheduledJobs> {\n'
        '                                SettingScheduledJobsPage()\n'
        '                            }\n'
    )
    t = t[:eidx] + new_entry + t[eidx + len(ANCHOR_ENTRY):]

    # 3. import
    if 'import me.rerere.rikkahub.ui.pages.setting.SettingScheduledJobsPage' not in t:
        anchor_import = 'import me.rerere.rikkahub.ui.pages.setting.SettingPage\n'
        if anchor_import not in t:
            # 回退：找任意 setting 包 import
            import re
            m = re.search(r'import me\.rerere\.rikkahub\.ui\.pages\.setting\.[A-Za-z0-9_]+\n', t)
            if not m:
                fail(P_ROUTE, "no setting import anchor found")
            t = t[:m.start()] + 'import me.rerere.rikkahub.ui.pages.setting.SettingScheduledJobsPage\n' + t[m.start():]
        else:
            t = t.replace(anchor_import,
                          anchor_import + 'import me.rerere.rikkahub.ui.pages.setting.SettingScheduledJobsPage\n', 1)

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
