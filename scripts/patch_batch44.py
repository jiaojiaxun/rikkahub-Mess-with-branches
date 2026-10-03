#!/usr/bin/env python3
'''batch44: 定时任务设置页搜索镜像 + 字符串资源（补 batch43 遗漏）

batch43 把 SettingScheduledJobsPage 接进了设置页和路由，但漏了两件事：
1. SettingPage.kt 头部 NOTE 写明 SettingsSearchIndex.kt 是设置项的
   手工镜像 —— 没同步的话，设置搜索页搜不到“定时任务”。
2. SettingsSearchEntry 的 titleRes 要求 @StringRes Int，而 batch43 的
   入口用的是硬编码中文字符串 —— 需要在 values/strings.xml 加资源。

顺手把 SettingPage 入口的硬编码中文换成资源引用，消除镜像不匹配。

锚点（已读全文件确认）：
- strings.xml：以 setting_page_workspace_files 为锚（batch 未动过该区域）
- SettingsSearchIndex.kt：以 route = Screen.SettingFiles 的 entry 结尾为锚
- SettingPage.kt：以 batch43 自己插入的 item 的三行文本为锚（字面锚,
  因为是我们自己写入的、格式完全可控）
全部幂等 + 存在性自检。
'''
from pathlib import Path
import re

ROOT = Path.cwd()

STR = "app/src/main/res/values/strings.xml"
IDX = "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingsSearchIndex.kt"
SP = "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPage.kt"


def fail(path, msg):
    print('::error file=' + path + '::batch44 ' + str(msg)[:1200])
    raise SystemExit(1)


# ---------- 1. strings.xml ----------
s = (ROOT / STR).read_text(encoding='utf-8')
if 'setting_page_scheduled_jobs' not in s:
    A = '    <string name="setting_page_workspace_files">'
    i = s.find(A)
    if i < 0:
        fail(STR, 'anchor setting_page_workspace_files not found')
    ins = (
        '    <string name="setting_page_scheduled_jobs">定时任务</string>\n'
        + '    <string name="setting_page_scheduled_jobs_desc">查看、开关、删除 AI 创建的定时任务</string>\n'
    )
    # 插在该行所在 string 标签结束之后
    end = s.find('</string>', i)
    if end < 0:
        fail(STR, 'malformed string tag near workspace_files')
    end += len('</string>') + 1  # +1 吃掉 \n
    t = s[:end] + ins + s[end:]
    (ROOT / STR).write_text(t, encoding='utf-8')
    print('batch44: strings.xml entries added')
else:
    print('batch44: strings.xml already patched')

# ---------- 2. SettingsSearchIndex.kt ----------
t = (ROOT / IDX).read_text(encoding='utf-8')
if 'Screen.SettingScheduledJobs' not in t:
    # 锚：SettingFiles 那条 entry 的收尾（已读真实代码，5 行缩进 8 空格）
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
        m.group(0)
        + m.group(1) + 'SettingsSearchEntry(\n'
        + m.group(2) + 'titleRes = R.string.setting_page_scheduled_jobs,\n'
        + m.group(3) + 'descriptionRes = R.string.setting_page_scheduled_jobs_desc,\n'
        + m.group(4) + 'groupRes = R.string.setting_page_data_settings,\n'
        + m.group(5) + 'route = Screen.SettingScheduledJobs,\n'
        + m.group(6) + '),\n'
    )
    t = t[:m.end()] + ins[m.end() - m.start() - len(m.group(0)):] + t[m.end():]
    # 上一行写法容易错，直接重构：在锚后插入
    t = (ROOT / IDX).read_text(encoding='utf-8')
    m2 = re.search(
        r'( *)SettingsSearchEntry\(\n'
        r'( *)titleRes = R\.string\.setting_files_page_title,\n'
        r'( *)descriptionRes = R\.string\.setting_page_chat_storage_desc,\n'
        r'( *)groupRes = R\.string\.setting_page_data_settings,\n'
        r'( *)route = Screen\.SettingFiles,\n'
        r'( *)\),\n',
        t,
    )
    if not m2:
        fail(IDX, 'anchor lost after first attempt (unexpected)')
    ins2 = (
        m2.group(1) + 'SettingsSearchEntry(\n'
        + m2.group(2) + 'titleRes = R.string.setting_page_scheduled_jobs,\n'
        + m2.group(3) + 'descriptionRes = R.string.setting_page_scheduled_jobs_desc,\n'
        + m2.group(4) + 'groupRes = R.string.setting_page_data_settings,\n'
        + m2.group(5) + 'route = Screen.SettingScheduledJobs,\n'
        + m2.group(6) + '),\n'
    )
    t = t[:m2.end()] + ins2 + t[m2.end():]
    (ROOT / IDX).write_text(t, encoding='utf-8')
    print('batch44: SettingsSearchIndex entry added')
else:
    print('batch44: SettingsSearchIndex already patched')

# ---------- 3. SettingPage.kt 换资源引用 ----------
u = (ROOT / SP).read_text(encoding='utf-8')
if 'setting_page_scheduled_jobs' not in u:
    # batch43 插的是硬编码中文；换成资源引用（两处文本行）
    old_h = 'supportingContent = { Text("查看、开关、删除 AI 创建的定时任务") },'
    new_h = 'supportingContent = { Text(stringResource(R.string.setting_page_scheduled_jobs_desc)) },'
    if old_h in u:
        u = u.replace(old_h, new_h, 1)
        print('batch44: SP supporting text swapped to resource')
    else:
        print('batch44: SP supporting anchor not found (may be already resource) — check next')
    old_t = 'headlineContent = { Text("定时任务") },'
    new_t = 'headlineContent = { Text(stringResource(R.string.setting_page_scheduled_jobs)) },'
    if old_t in u:
        u = u.replace(old_t, new_t, 1)
        print('batch44: SP headline text swapped to resource')
    else:
        if new_t not in u:
            fail(SP, 'neither hardcoded nor resource form found for headline')
    (ROOT / SP).write_text(u, encoding='utf-8')
else:
    print('batch44: SP already using resources')

# ---------- 自检 ----------
s2 = (ROOT / STR).read_text(encoding='utf-8')
for need in [
    '<string name="setting_page_scheduled_jobs">定时任务</string>',
    '<string name="setting_page_scheduled_jobs_desc">查看、开关、删除 AI 创建的定时任务</string>',
]:
    if need not in s2:
        fail(STR, 'selfcheck missing: ' + need[:60])

i2 = (ROOT / IDX).read_text(encoding='utf-8')
for need in [
    'titleRes = R.string.setting_page_scheduled_jobs,',
    'route = Screen.SettingScheduledJobs,',
]:
    if need not in i2:
        fail(IDX, 'selfcheck missing: ' + need[:60])

u2 = (ROOT / SP).read_text(encoding='utf-8')
if 'Text(stringResource(R.string.setting_page_scheduled_jobs))' not in u2:
    fail(SP, 'selfcheck: SP entry not using resource')

print('batch44: ALL OK')
