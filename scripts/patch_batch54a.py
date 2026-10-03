#!/usr/bin/env python3
'''batch54a: 设置页接入精简版流式开关（batch53 的 UI 补完）

SettingPreferencesUIPage「消息显示」组，enableLatexRendering 开关后插入
liteStreamRender 开关（模式完全照抄同组现有 item）。

锚点（2026-10-03 真实读取，链后形态核查：batch3 在该文件只加过
collapseLongUserMessage（后面的组）——enableLatexRendering 段是原始形态，安全）：
- UIPage: enableLatexRendering item 的完整块（headline+supporting+Switch）
- strings.xml (en+zh): <resources> 开标签后插入（batch44 v2 验证过的稳点；本轮 strings 配额无其他脚本占用）

铁律：零反斜杠；幂等 marker；自检双向。'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhLiteStreamSwitch'


def fail(path, msg):
    print('::error file=' + path + '::batch54a ' + str(msg)[:1500])
    raise SystemExit(1)


# ============================================================
# 1. strings.xml（en + zh 双份）
# ============================================================
STRS = [
    ('app/src/main/res/values/strings.xml',
     'Lite streaming render',
     'Stream the in-progress message as plain text (skips Markdown and thinking-card animations); switches back to full rendering when generation finishes. Helps with long-session lag.'),
    ('app/src/main/res/values-zh/strings.xml',
     '精简版流式渲染',
     '流式中的末条消息按纯文本直出（跳过 Markdown 与思考卡片动画），生成完成自动切回完整渲染。长会话防卡顿。'),
]
for path, title, desc in STRS:
    s = (ROOT / path).read_text(encoding='utf-8')
    if 'rh_lite_stream_render_title' in s:
        print('batch54a: strings already patched: ' + path)
        continue
    i = s.find('<resources')
    if i < 0:
        fail(path, 'no resources tag')
    j = s.find('>', i)
    if j < 0:
        fail(path, 'resources tag not closed')
    ins = (NL + '    <!-- ' + MARK + ' -->' + NL +
           '    <string name="rh_lite_stream_render_title">' + title + '</string>' + NL +
           '    <string name="rh_lite_stream_render_desc">' + desc + '</string>')
    s = s[:j + 1] + ins + s[j + 1:]
    (ROOT / path).write_text(s, encoding='utf-8')
    print('batch54a: strings OK: ' + path)

# ============================================================
# 2. SettingPreferencesUIPage.kt — enableLatexRendering 后插开关
# ============================================================
UI = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPreferencesUIPage.kt'
u = (ROOT / UI).read_text(encoding='utf-8')
if MARK not in u:
    OLD = (
        '                    item(' + NL +
        '                        headlineContent = { Text(stringResource(R.string.setting_display_page_enable_latex_rendering_title)) },' + NL +
        '                        supportingContent = { Text(stringResource(R.string.setting_display_page_enable_latex_rendering_desc)) },' + NL +
        '                        trailingContent = {' + NL +
        '                            Switch(' + NL +
        '                                checked = displaySetting.enableLatexRendering,' + NL +
        '                                onCheckedChange = {' + NL +
        '                                    updateDisplaySetting(displaySetting.copy(enableLatexRendering = it))' + NL +
        '                                }' + NL +
        '                            )' + NL +
        '                        },' + NL +
        '                    )'
    )
    NEW = (
        '                    item(' + NL +
        '                        headlineContent = { Text(stringResource(R.string.setting_display_page_enable_latex_rendering_title)) },' + NL +
        '                        supportingContent = { Text(stringResource(R.string.setting_display_page_enable_latex_rendering_desc)) },' + NL +
        '                        trailingContent = {' + NL +
        '                            Switch(' + NL +
        '                                checked = displaySetting.enableLatexRendering,' + NL +
        '                                onCheckedChange = {' + NL +
        '                                    updateDisplaySetting(displaySetting.copy(enableLatexRendering = it))' + NL +
        '                                }' + NL +
        '                            )' + NL +
        '                        },' + NL +
        '                    )' + NL +
        '                    // ' + MARK + ' (batch54a): 精简版流式渲染开关' + NL +
        '                    item(' + NL +
        '                        headlineContent = { Text(stringResource(R.string.rh_lite_stream_render_title)) },' + NL +
        '                        supportingContent = { Text(stringResource(R.string.rh_lite_stream_render_desc)) },' + NL +
        '                        trailingContent = {' + NL +
        '                            Switch(' + NL +
        '                                checked = displaySetting.liteStreamRender,' + NL +
        '                                onCheckedChange = {' + NL +
        '                                    updateDisplaySetting(displaySetting.copy(liteStreamRender = it))' + NL +
        '                                }' + NL +
        '                            )' + NL +
        '                        },' + NL +
        '                    )'
    )
    if OLD not in u:
        fail(UI, 'latex item anchor not found')
    if u.count(OLD) != 1:
        fail(UI, 'latex item anchor not unique: ' + str(u.count(OLD)))
    u = u.replace(OLD, NEW, 1)
    for need in [MARK, 'displaySetting.liteStreamRender', 'R.string.rh_lite_stream_render_title']:
        if need not in u:
            fail(UI, 'selfcheck missing: ' + need)
    (ROOT / UI).write_text(u, encoding='utf-8')
    print('batch54a: UIPage OK')
else:
    print('batch54a: UIPage already applied')

print('batch54a: OK')
