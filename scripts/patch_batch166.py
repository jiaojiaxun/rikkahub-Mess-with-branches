#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch166: 字体全局应用(warn-only)

用户反馈: 字体应用只能作用在聊天页面,其他字段不能变字体。

根因: Theme.kt 的 RikkahubTheme 里 typography = Typography(Type.kt 的默认值)——
没有应用自定义字体。聊天页面通过 LocalChatFontFamily 单独应用了字体,其他页面没拿到。

修法:
1. Type.kt 加 withCustomFontFamily 扩展函数(把 FontFamily 应用到全部排版样式)
2. Theme.kt 在 RikkahubTheme 里解析字体并应用到 typography

warn-only: 任何锚点失败只 ::warning + 跳过,不阻塞构建(多人协作)。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhGlobalFont'
TY = 'app/src/main/java/me/rerere/rikkahub/ui/theme/Type.kt'
TH = 'app/src/main/java/me/rerere/rikkahub/ui/theme/Theme.kt'


def warn(msg, path):
    print('::warning file=' + path + '::batch166 ' + str(msg)[:1200])


def skip(msg, path):
    warn(msg + ' — skipped (warn-only)', path)
    sys.stdout.flush()
    sys.exit(0)


def balance(text):
    return text.count('(') - text.count(')') + (text.count('{') - text.count('}'))


# ---- 1. Type.kt 加 withCustomFontFamily 扩展函数 ----
try:
    ty = (ROOT / TY).read_text(encoding='utf-8')
except Exception as e:
    skip('read Type.kt failed: ' + str(e), TY)

if MARK not in ty:
    lines = ty.split(NL)
    bal0 = balance(ty)
    # 找 JetbrainsMono 定义作为插入点(在它之前插入)
    hits = [i for i, ln in enumerate(lines) if ln.strip().startswith('val JetbrainsMono')]
    if len(hits) != 1:
        skip('JetbrainsMono anchor count=' + str(len(hits)), TY)
    ti = hits[0]
    ext_fn = [
        '// ' + MARK + ': 把自定义字体应用到全部排版样式(全局字体支持)',
        'fun Typography.withCustomFontFamily(fontFamily: FontFamily): Typography = copy(',
        '    displayLarge = displayLarge.copy(fontFamily = fontFamily),',
        '    displayMedium = displayMedium.copy(fontFamily = fontFamily),',
        '    displaySmall = displaySmall.copy(fontFamily = fontFamily),',
        '    headlineLarge = headlineLarge.copy(fontFamily = fontFamily),',
        '    headlineMedium = headlineMedium.copy(fontFamily = fontFamily),',
        '    headlineSmall = headlineSmall.copy(fontFamily = fontFamily),',
        '    titleLarge = titleLarge.copy(fontFamily = fontFamily),',
        '    titleMedium = titleMedium.copy(fontFamily = fontFamily),',
        '    titleSmall = titleSmall.copy(fontFamily = fontFamily),',
        '    bodyLarge = bodyLarge.copy(fontFamily = fontFamily),',
        '    bodyMedium = bodyMedium.copy(fontFamily = fontFamily),',
        '    bodySmall = bodySmall.copy(fontFamily = fontFamily),',
        '    labelLarge = labelLarge.copy(fontFamily = fontFamily),',
        '    labelMedium = labelMedium.copy(fontFamily = fontFamily),',
        '    labelSmall = labelSmall.copy(fontFamily = fontFamily),',
        ')',
        '',
    ]
    for j, b in enumerate(ext_fn):
        lines.insert(ti + j, b)
    out = NL.join(lines)
    if MARK not in out or balance(out) != bal0:
        skip('Type.kt selfcheck failed', TY)
    (ROOT / TY).write_text(out, encoding='utf-8')
    print('batch166: Type.kt OK (withCustomFontFamily added)')
else:
    print('batch166: Type.kt already applied')

# ---- 2. Theme.kt 应用全局字体 ----
try:
    th = (ROOT / TH).read_text(encoding='utf-8')
except Exception as e:
    skip('read Theme.kt failed: ' + str(e), TH)

if MARK not in th:
    lines = th.split(NL)
    bal0 = balance(th)

    # 2a. 加 import(FontFamily)
    if 'import androidx.compose.ui.text.font.FontFamily' not in th:
        ip = -1
        for i, ln in enumerate(lines):
            if ln.strip() == 'import androidx.compose.ui.graphics.Color':
                ip = i
                break
        if ip < 0:
            skip('Color import anchor not found', TH)
        lines.insert(ip + 1, 'import androidx.compose.ui.text.font.FontFamily // ' + MARK)

    # 2b. 在 settings 声明后加字体解析
    hits = [i for i, ln in enumerate(lines) if 'val settings by rememberUserSettingsState()' in ln]
    if len(hits) != 1:
        skip('settings anchor count=' + str(len(hits)), TH)
    si = hits[0]
    d = lines[si][:len(lines[si]) - len(lines[si].lstrip())]
    font_block = [
        '',
        d + '// ' + MARK + ': 全局字体(应用到所有页面的排版)',
        d + 'val rhFontContext = LocalContext.current',
        d + 'val rhGlobalFontFamily = remember(settings.displaySetting.chatFontFamily, settings.displaySetting.chatCustomFontPath) {',
        d + '    settings.displaySetting.resolveChatFontFamily(rhFontContext)',
        d + '}',
        d + 'val rhGlobalTypography = remember(rhGlobalFontFamily) {',
        d + '    if (rhGlobalFontFamily == FontFamily.Default) Typography',
        d + '    else Typography.withCustomFontFamily(rhGlobalFontFamily)',
        d + '}',
    ]
    for j, b in enumerate(font_block):
        lines.insert(si + 1 + j, b)

    # 2c. 把 typography = Typography 改成 rhGlobalTypography
    hits = [i for i, ln in enumerate(lines) if ln.strip() == 'typography = Typography,']
    if len(hits) != 1:
        skip('typography anchor count=' + str(len(hits)), TH)
    ti = hits[0]
    lines[ti] = lines[ti].replace('typography = Typography,', 'typography = rhGlobalTypography, // ' + MARK)

    out = NL.join(lines)
    for need in [MARK, 'rhGlobalFontFamily', 'rhGlobalTypography', 'withCustomFontFamily']:
        if need not in out:
            skip('selfcheck missing: ' + need, TH)
    if balance(out) != bal0:
        skip('Theme.kt balance changed', TH)
    (ROOT / TH).write_text(out, encoding='utf-8')
    print('batch166: Theme.kt OK (global font applied)')
else:
    print('batch166: Theme.kt already applied')

print('batch166: OK')
