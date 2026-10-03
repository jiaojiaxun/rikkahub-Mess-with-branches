#!/usr/bin/env python3
'''batch43: 定时任务设置页接线（补 4 处缺口）

诊断（2026-10-03 读真实代码确认）：
  SettingScheduledJobsPage.kt（batch37 新建）功能完整（列表/开关/详情/立即执行/删除/历史），
  但完全孤立不可达 —— 4 处接线全缺：
    1. RouteActivity.kt import 区没有 SettingScheduledJobsPage
    2. RouteActivity.kt Screen sealed interface 没有 SettingScheduledJobs
    3. RouteActivity.kt entryProvider 没有对应 entry
    4. SettingPage.kt 没有入口 item（五个卡组都不是）
  → 用户根本打不开这个页面。DI 已由 batch38 补齐，本脚本只做接线。

锚点选择（铁律12：列对齐代码不用逐字空格，用行级正则推导缩进）：
  - import 锚：SettingWebPage（import 无对齐问题，直接字符串）
  - Screen 锚：data object SettingToolApprovals : Screen
  - entry 锚：entry<Screen.SettingToolApprovals> 块（缩进由捕获组推导）
  - 入口锚：SettingFiles item（缩进由捕获组推导）
幂等：每处独立 marker，已存在则跳过；改完统一自检 4 项。
'''
from pathlib import Path
import re

ROOT = Path.cwd()
RA = "app/src/main/java/me/rerere/rikkahub/RouteActivity.kt"
SP = "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPage.kt"


def fail(path, msg):
    print('::error file=' + path + '::batch43 ' + str(msg)[:1200])
    raise SystemExit(1)


# ---------- RouteActivity.kt ----------
t = (ROOT / RA).read_text(encoding='utf-8')
if 'SettingScheduledJobsPage' not in t:
    A_IMP = 'import me.rerere.rikkahub.ui.pages.setting.SettingWebPage\n'
    if A_IMP not in t:
        fail(RA, 'import anchor SettingWebPage not found')
    t = t.replace(A_IMP, A_IMP + 'import me.rerere.rikkahub.ui.pages.setting.SettingScheduledJobsPage\n', 1)
    print('batch43: RA import added')
else:
    print('batch43: RA import already present')

if 'data object SettingScheduledJobs' not in t:
    m = re.search(r'\n([ \t]*)@Serializable\n[ \t]*data object SettingToolApprovals : Screen\n', t)
    if not m:
        fail(RA, 'Screen anchor SettingToolApprovals not found')
    ind = m.group(1)
    ins = '\n' + ind + '@Serializable\n' + ind + 'data object SettingScheduledJobs : Screen\n'
    t = t[:m.end()] + ins + t[m.end():]
    print('batch43: RA Screen object added')
else:
    print('batch43: RA Screen object already present')

if 'entry<Screen.SettingScheduledJobs>' not in t:
    m = re.search(
        r'([ \t]*)entry<Screen\.SettingToolApprovals>[\s\S]*?'
        r'SettingToolApprovalsPage\(\)[ \t]*\n[ \t]*\}[ \t]*\n',
        t,
    )
    if not m:
        fail(RA, 'entry anchor SettingToolApprovals entry not found')
    ind = m.group(1)
    ins = (
        ind + 'entry<Screen.SettingScheduledJobs> {\n'
        + ind + '    SettingScheduledJobsPage()\n'
        + ind + '}\n'
    )
    t = t[:m.end()] + ins + t[m.end():]
    print('batch43: RA entry added')
else:
    print('batch43: RA entry already present')

for need in [
    'import me.rerere.rikkahub.ui.pages.setting.SettingScheduledJobsPage\n',
    'data object SettingScheduledJobs : Screen',
    'entry<Screen.SettingScheduledJobs>',
    'SettingScheduledJobsPage()\n',
]:
    if need not in t:
        fail(RA, 'RA selfcheck missing: ' + repr(need))
(ROOT / RA).write_text(t, encoding='utf-8')
print('batch43: RouteActivity.kt written OK')


# ---------- SettingPage.kt ----------
s = (ROOT / SP).read_text(encoding='utf-8')
if 'Screen.SettingScheduledJobs' not in s:
    m = re.search(
        r'([ \t]*)item\(\n[ \t]*onClick = \{ navController\.navigate\(Screen\.SettingFiles\) \},'
        r'[\s\S]*?headlineContent = \{ Text\(stringResource\(R\.string\.setting_page_workspace_files\)\) \},\n'
        r'[ \t]*\)\n',
        s,
    )
    if not m:
        fail(SP, 'entry item anchor SettingFiles not found')
    ind = m.group(1)          # 'item(' 的缩进
    inner = ind + '    '      # 子参数缩进
    ins = (
        ind + 'item(\n'
        + inner + 'onClick = { navController.navigate(Screen.SettingScheduledJobs) },\n'
        + inner + 'leadingContent = { Icon(HugeIcons.Clock02, null) },\n'
        + inner + 'supportingContent = { Text("\u67e5\u770b\u3001\u5f00\u5173\u3001\u5220\u9664 AI \u521b\u5efa\u7684\u5b9a\u65f6\u4efb\u52a1") },\n'
        + inner + 'headlineContent = { Text("\u5b9a\u65f6\u4efb\u52a1") },\n'
        + ind + ')\n'
    )
    s = s[:m.end()] + ins + s[m.end():]
    print('batch43: SP entry item added')
else:
    print('batch43: SP entry item already present')

for need in [
    'navController.navigate(Screen.SettingScheduledJobs)',
    'HugeIcons.Clock02',
]:
    if need not in s:
        fail(SP, 'SP selfcheck missing: ' + repr(need))
# Clock02 必须已 import，否则 Unresolved reference
if 'import me.rerere.hugeicons.stroke.Clock02' not in s:
    fail(SP, 'Clock02 icon not imported in SettingPage.kt')
(SP / '.').parent.mkdir(exist_ok=True, parents=True) if False else None
(SP / '..').mkdir(exist_ok=True) if False else None
(ROOT / SP).write_text(s, encoding='utf-8')
print('batch43: SettingPage.kt written OK')

print('batch43: ALL 4 HOOKUPS OK')
