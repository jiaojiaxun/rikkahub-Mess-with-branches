#!/usr/bin/env python3
'''batch44 v2: 定时任务搜索镜像 + 字符串资源（英文+中文双份）

v1 失败：`anchor setting_page_workspace_files not found`
根因（读真实文件确认）：
  1. strings.xml 缩进是 2 空格，不是 4
  2. 默认 values/strings.xml 是英文，根本没有 setting_page_workspace_files 这个 key
     （SettingPage.kt 用的是 setting_page_chat_storage；
     SettingsSearchIndex 里 workspace 行用 titleRes=setting_files_page_title）
  3. 中文文案在 values-zh/strings.xml，两份都要加，否则英文环境 fallback 到 key

v2 策略：
  - 锚点改用两个文件里都真实存在的 key：setting_page_data_settings
    （刚读过：values/ 和 values-zh/ 都有，且按字典序排列，setting_page_scheduled_jobs
    按字母序应插在它前面）
  - 插入位置用「插入到 <resources> 开标签之后」，最稳（不依赖排序）
  - SettingPage.kt 的硬编码中文换成资源引用（batch43 插入的行是字面锚，格式可控）
  - SettingsSearchIndex.kt 锚：route = Screen.SettingFiles 那条 entry（已读，真实存在）
全部幂等 + 存在性自检。
'''
from pathlib import Path
import re

ROOT = Path.cwd()

STR_EN = "app/src/main/res/values/strings.xml"
STR_ZH = "app/src/main/res/values-zh/strings.xml"
IDX = "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingsSearchIndex.kt"
SP = "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPage.kt"


def fail(path, msg):
    print('::error file=' + path + '::batch44 ' + str(msg)[:1200])
    raise SystemExit(1)


def add_strings(path, two_lines):
    s = (ROOT / path).read_text(encoding='utf-8')
    if 'setting_page_scheduled_jobs' in s:
        print('batch44: ' + path + ' already patched')
        return
    marker = '<resources>'
    i = s.find(marker)
    if i < 0:
        fail(path, '<resources> tag not found')
    ins = '\n' + two_lines
    t = s[:i + len(marker)] + ins + s[i + len(marker):]
    (ROOT / path).write_text(t, encoding='utf-8')
    print('batch44: ' + path + ' entries added')


# ---------- 1. 英文默认资源 ----------
add_strings(
    STR_EN,
    '  <string name="setting_page_scheduled_jobs">Scheduled Jobs</string>\n'
    '  <string name="setting_page_scheduled_jobs_desc">View, toggle or delete AI-created scheduled jobs</string>',
)

# ---------- 2. 中文资源 ----------
add_strings(
    STR_ZH,
    '  <string name="setting_page_scheduled_jobs">定时任务</string>\n'
    '  <string name="setting_page_scheduled_jobs_desc">查看、开关、删除 AI 创建的定时任务</string>',
)

# ---------- 3. SettingsSearchIndex.kt ----------
t = (ROOT / IDX).read_text(encoding='utf-8')
if 'Screen.SettingScheduledJobs' not in t:
    m = re.search(
        r'( *)SettingsSearchEntry\(\n'
        r'( *)titleRes = R\.string\.setting_files_page_title,\n'
        r'( *)descriptionRes = R\.string\.setting_page_chat_storage_desc,\n'
        r'( *)groupRes = R\.string\.setting_page_data_settings,\n'
        r'( *)route = Screen\.SettingFiles,\n'
        r'( *)\),\n',
        t,
    )
    if not m:
        fail(IDX, 'anchor SettingFiles entry not found')
    ins = (
        m.group(1) + 'SettingsSearchEntry(\n'
        + m.group(2) + 'titleRes = R.string.setting_page_scheduled_jobs,\n'
        + m.group(3) + 'descriptionRes = R.string.setting_page_scheduled_jobs_desc,\n'
        + m.group(4) + 'groupRes = R.string.setting_page_data_settings,\n'
        + m.group(5) + 'route = Screen.SettingScheduledJobs,\n'
        + m.group(6) + '),\n'
    )
    t = t[:m.end()] + ins + t[m.end():]
    (ROOT / IDX).write_text(t, encoding='utf-8')
    print('batch44: SettingsSearchIndex entry added')
else:
    print('batch44: SettingsSearchIndex already patched')

# ---------- 4. SettingPage.kt 换资源引用 ----------
u = (ROOT / SP).read_text(encoding='utf-8')
if 'stringResource(R.string.setting_page_scheduled_jobs)' not in u:
    old_h = 'supportingContent = { Text("查看、开关、删除 AI 创建的定时任务") },'
    new_h = 'supportingContent = { Text(stringResource(R.string.setting_page_scheduled_jobs_desc)) },'
    if old_h in u:
        u = u.replace(old_h, new_h, 1)
        print('batch44: SP supporting text swapped')
    else:
        # batch43 插入时若因转义不同而未命中，则查是否存在旧式插入的迹象
        if 'setting_page_scheduled_jobs_desc' not in u:
            fail(SP, 'SP supporting anchor not found')

    old_t = 'headlineContent = { Text("定时任务") },'
    new_t = 'headlineContent = { Text(stringResource(R.string.setting_page_scheduled_jobs)) },'
    if old_t in u:
        u = u.replace(old_t, new_t, 1)
        print('batch44: SP headline text swapped')
    else:
        if 'setting_page_scheduled_jobs' not in u:
            fail(SP, 'SP headline anchor not found')
    (ROOT / SP).write_text(u, encoding='utf-8')
else:
    print('batch44: SP already using resources')

# ---------- 自检 ----------
for p, need in [
    (STR_EN, '<string name="setting_page_scheduled_jobs">Scheduled Jobs</string>'),
    (STR_EN, 'setting_page_scheduled_jobs_desc'),
    (STR_ZH, '<string name="setting_page_scheduled_jobs">定时任务</string>'),
    (STR_ZH, 'setting_page_scheduled_jobs_desc'),
]:
    if need not in (ROOT / p).read_text(encoding='utf-8'):
        fail(p, 'selfcheck missing: ' + need[:60])

i2 = (ROOT / IDX).read_text(encoding='utf-8')
for need in [
    'titleRes = R.string.setting_page_scheduled_jobs,',
    'route = Screen.SettingScheduledJobs,',
]:
    if need not in i2:
        fail(IDX, 'selfcheck missing: ' + need[:60])

u2 = (ROOT / SP).read_text(encoding='utf-8')
if 'stringResource(R.string.setting_page_scheduled_jobs)' not in u2:
    fail(SP, 'selfcheck: SP not using resource')

print('batch44 v2: ALL OK')
