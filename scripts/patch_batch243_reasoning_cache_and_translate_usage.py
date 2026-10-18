#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch243: T-S4 reasoning 正则缓存 + T9 翻译场景使用时间打点 + #9/#6 现场取证

本批由两部分组成，刻意合并推一次以省 CI：
  A. 两个修复（锚点全部来自 snapshot 真形态实读）
  B. 两个现场取证（只 dump 不改动，为下一批精准修改拿真实内容）

--------------------------------------------------------------------------
A1. T-S4 —— ChatMessageReasoning.kt 的每帧全文正则
实读真形态(ChatMessageReasoning.kt / ReasoningContent):
    val reasoningContent = @Composable {
        MarkdownBlock(
            content = reasoning.reasoning.replaceRegexes(
                assistant = assistant,
                scope = AssistantAffectScope.ASSISTANT,
                visual = true,
            ),
            style = reasoningTextStyle,
            modifier = Modifier.fillMaxSize(),
        )
    }
=> replaceRegexes 在**每次重组**时对整个 reasoning 文本重跑，与文本是否变化无关:
   滚动、展开/折叠、主题或字号变化、父级任何重组都会触发全文正则。
修复: 用 remember 把结果按 (文本, 助手 id, 助手 regexes) 缓存。
   文本变化(流式增长)仍会重算 —— 这是正确且必需的; 但非文本触发的重组不再重算。
   视觉零变化: 渲染的仍是同一份替换后文本。

A2. T9 —— 翻译场景不记录供应商最后一次调用时间
实读真形态(batch92 打点链路):
   - AILogging.kt 已有 `fun recordProviderUsed(providerId: Uuid)`(30 秒节流)
   - GenerationHandler.kt 在 `val providerImpl = providerManager.getProviderByType(provider)`
     之后调用 `aiLoggingManager.recordProviderUsed(provider.id) // rhProviderTidy`
   - 但 TranslationHandler.translateText 直接调 providerHandler.streamText / generateText,
     完全绕过 GenerationHandler => 翻译过的供应商不会更新"最后调用时间",
     导致供应商"一键整理"的组内时间排序对翻译场景失效。
修复: 给 TranslationHandler 注入 AILoggingManager, 在 provider 解析后同样打点。
   TranslationHandler 与 AILoggingManager 同属 me.rerere.rikkahub.data.ai 包 => 零新增 import。
   DI 侧 AppModule 已有 `import ...AILoggingManager` => 零新增 import, 只改一行 get() 调用。

--------------------------------------------------------------------------
B1. #9 LITE「转文件」文案 —— 只取证不改
用户反馈"没看懂 LITE 转文件是什么意思"。strings.xml(zh) 有 142KB, 无法安全整读,
故本批扫描并 dump 所有含关键词的字符串条目(不修改), 下一批按真实内容精准改写。
关键词: 转文件 / 存成文件 / LITE / lite

B2. #6 定时任务"两个" —— 只取证不改
已实读 SettingPage.kt: advancedServices 内 `Screen.SettingScheduledJobs` 入口**只有 1 个**
(标了 // rhCronEntry)。本批再扫描全部 .kt 里对 SettingScheduledJobs 的引用并 dump 计数,
用于判定"两个"到底是"两个入口"还是"任务列表里两条记录"。

--------------------------------------------------------------------------
五查:
  1. import 清单: ChatMessageReasoning.kt 的 remember 已 import; TranslationHandler/AppModule
     所需符号同包或已 import => 三处均零新增 import
  2. 同文件冲突: 三个源文件均无在链 patch 触碰(批量审计: batch92 改的是 GenerationHandler/AILogging/
     PreferencesStore/SettingProviderPage; 本批不碰这四个)
  3. 作用域: reasoningVisualText 插在 ReasoningContent 内, reasoning/assistant/reasoningTextStyle
     均在同一作用域; aiLoggingManager 为类成员
  4. 括号配对: 逐文件断言修改前后 balance 完全一致
  5. 函数签名: 只给 TranslationHandler 主构造增加一个参数(Koin single 同步更新),
     其余函数签名零改动
Python 三查: Q/SQ/D 变量构造引号; NL 显式 concat 禁 join/f-string/walrus;
helper 先定义后用; 锚点行级 strip 匹配; 失败 ::error + exit(1)
'''
import re
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
D = chr(34)
SQ = chr(39)
MARK = 'rhBatch243'

REASONING = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageReasoning.kt'
TRANSLATION = 'app/src/main/java/me/rerere/rikkahub/data/ai/TranslationHandler.kt'
APPMODULE = 'app/src/main/java/me/rerere/rikkahub/di/AppModule.kt'
STRINGS_ZH = 'app/src/main/res/values-zh/strings.xml'
STRINGS_EN = 'app/src/main/res/values/strings.xml'
SETTING_PAGE = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPage.kt'

report = []


def fail(msg):
    print('::error::batch243 ' + str(msg)[:1500])
    sys.stdout.flush()
    sys.exit(1)


def note(msg):
    report.append(str(msg))


def balance(text):
    return (text.count('(') - text.count(')')
            + text.count('{') - text.count('}')
            + text.count('[') - text.count(']'))


def lines_to_text(lines):
    out = ''
    for idx, line in enumerate(lines):
        if idx > 0:
            out += NL
        out += line
    return out


def ind_of(line):
    s = line.lstrip()
    return line[:len(line) - len(s)]


def find_line(lines, needle, label, start=0, end=-1):
    if end < 0:
        end = len(lines)
    hits = [i for i in range(start, min(end, len(lines))) if lines[i].strip() == needle]
    if len(hits) == 0:
        fail(label + ': line not found -> ' + repr(needle))
    if len(hits) != 1:
        fail(label + ': line count=' + str(len(hits)) + ' expected 1 -> ' + repr(needle))
    return hits[0]


# ===========================================================================
# A1. ChatMessageReasoning.kt
# ===========================================================================
def patch_reasoning():
    p = ROOT / REASONING
    if not p.exists():
        fail('ChatMessageReasoning.kt missing')
    t = p.read_text(encoding='utf-8')
    if 'rhReasoningRegCache243' in t:
        note('A1 reasoning already applied, skip')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    content_idx = find_line(lines, 'content = reasoning.reasoning.replaceRegexes(',
                            'reasoning replaceRegexes call')
    expect = [
        'assistant = assistant,',
        'scope = AssistantAffectScope.ASSISTANT,',
        'visual = true,',
        '),',
    ]
    for off, want in enumerate(expect):
        got = lines[content_idx + 1 + off].strip()
        if got != want:
            fail('reasoning: expected line ' + str(off + 1) + ' = ' + repr(want)
                 + ' but got ' + repr(got))
    ci = ind_of(lines[content_idx])

    holder_idx = find_line(lines, 'val reasoningContent = @Composable {',
                           'reasoningContent holder')
    hi = ind_of(lines[holder_idx])

    pre = []
    pre.append(hi + '// rhReasoningRegCache243: 正则替换结果按 (文本, 助手) 缓存。')
    pre.append(hi + '// 原实现每次重组都重跑整段 reasoning 的 replaceRegexes —— 滚动/展开折叠/')
    pre.append(hi + '// 主题字号变化等任何重组都会触发全文正则, 与文本是否变化无关。')
    pre.append(hi + '// 文本变化(流式增长)仍会重算; 渲染内容与修复前逐字节相同。')
    pre.append(hi + 'val reasoningVisualText = remember(')
    pre.append(hi + '    reasoning.reasoning,')
    pre.append(hi + '    assistant?.id,')
    pre.append(hi + '    assistant?.regexes,')
    pre.append(hi + ') {')
    pre.append(hi + '    reasoning.reasoning.replaceRegexes(')
    pre.append(hi + '        assistant = assistant,')
    pre.append(hi + '        scope = AssistantAffectScope.ASSISTANT,')
    pre.append(hi + '        visual = true,')
    pre.append(hi + '    )')
    pre.append(hi + '}')

    replace_line = ci + 'content = reasoningVisualText,'
    if content_idx >= holder_idx:
        fail('reasoning: unexpected layout (call before holder)')

    lines = lines[:content_idx] + [replace_line] + lines[content_idx + 5:]
    holder_idx = find_line(lines, 'val reasoningContent = @Composable {', 'reasoningContent holder v2')
    lines = lines[:holder_idx] + pre + lines[holder_idx:]

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        fail('reasoning: balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
    if 'content = reasoning.reasoning.replaceRegexes(' in t2:
        fail('reasoning: old inline regex call still present')
    if 'val reasoningVisualText = remember(' not in t2:
        fail('reasoning: cache holder missing')
    if t2.count('reasoning.reasoning.replaceRegexes(') != 1:
        fail('reasoning: replaceRegexes call count=' + str(t2.count('reasoning.reasoning.replaceRegexes(')))
    if 'content = reasoningVisualText,' not in t2:
        fail('reasoning: MarkdownBlock content not rewired')
    p.write_text(t2, encoding='utf-8')
    note('A1 ChatMessageReasoning OK (remembered regex result)')


# ===========================================================================
# A2. TranslationHandler.kt + AppModule.kt
# ===========================================================================
def patch_translation():
    p = ROOT / TRANSLATION
    if not p.exists():
        fail('TranslationHandler.kt missing')
    t = p.read_text(encoding='utf-8')
    if 'rhTranslateUsageT9' in t:
        note('A2 translation already applied, skip')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    # 1. 主构造增加参数(同包, 零 import)
    ctor_idx = find_line(lines, 'private val providerManager: ProviderManager,',
                         'TranslationHandler ctor param')
    ci = ind_of(lines[ctor_idx])
    lines.insert(ctor_idx + 1, ci + 'private val aiLoggingManager: AILoggingManager, // rhTranslateUsageT9')

    # 2. provider 解析后打点
    handler_idx = find_line(lines, 'val providerHandler = providerManager.getProviderByType(provider)',
                            'translation providerHandler line')
    hi = ind_of(lines[handler_idx])
    lines.insert(handler_idx + 1,
                 hi + 'aiLoggingManager.recordProviderUsed(provider.id) // rhTranslateUsageT9')

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        fail('translation: balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
    for need in ['private val aiLoggingManager: AILoggingManager,',
                 'aiLoggingManager.recordProviderUsed(provider.id)']:
        if need not in t2:
            fail('translation: selfcheck missing ' + need)
    if t2.count('recordProviderUsed') != 1:
        fail('translation: recordProviderUsed count=' + str(t2.count('recordProviderUsed')))
    p.write_text(t2, encoding='utf-8')
    note('A2 TranslationHandler OK (usage recorded)')

    # 3. DI 更新
    ap = ROOT / APPMODULE
    if not ap.exists():
        fail('AppModule.kt missing')
    a = ap.read_text(encoding='utf-8')
    if 'rhTranslateUsageT9' in a:
        note('A2 AppModule already applied, skip')
        return
    bal0a = balance(a)
    alines = a.split(NL)
    di_idx = find_line(alines, 'single { TranslationHandler(get()) }', 'AppModule TranslationHandler single')
    dline = ind_of(alines[di_idx])
    alines[di_idx] = (dline + 'single { TranslationHandler(get(), get<AILoggingManager>()) } '
                      '// rhTranslateUsageT9')
    a2 = lines_to_text(alines)
    if balance(a2) != bal0a:
        fail('appmodule: balance changed ' + str(bal0a) + ' -> ' + str(balance(a2)))
    if 'TranslationHandler(get(), get<AILoggingManager>())' not in a2:
        fail('appmodule: TranslationHandler wiring missing')
    if a2.count('TranslationHandler(get())') != 0:
        fail('appmodule: old TranslationHandler wiring still present')
    if 'import me.rerere.rikkahub.data.ai.AILoggingManager' not in a2:
        fail('appmodule: AILoggingManager import missing (needed by explicit get<T>())')
    ap.write_text(a2, encoding='utf-8')
    note('A2 AppModule OK (TranslationHandler(get(), get<AILoggingManager>()))')


# ===========================================================================
# B1. #9 LITE / 转文件 文案取证(只 dump 不改)
# ===========================================================================
def dump_strings():
    keys = ['转文件', '存成文件', '转为文件', 'LITE', 'lite', 'Lite']
    for rel in [STRINGS_ZH, STRINGS_EN]:
        p = ROOT / rel
        if not p.exists():
            note('B1 ' + rel + ' NOT FOUND')
            continue
        text = p.read_text(encoding='utf-8')
        hits = []
        for i, line in enumerate(text.split(NL)):
            s = line.strip()
            if not s.startswith('<string'):
                continue
            for k in keys:
                if k in s:
                    hits.append('L' + str(i + 1) + ' ' + s[:150])
                    break
        note('B1 ' + rel + ' hits=' + str(len(hits)))
        for h in hits[:14]:
            note('B1 | ' + h)


# ===========================================================================
# B2. #6 SettingScheduledJobs 引用计数取证(只 dump 不改)
# ===========================================================================
def dump_cron_refs():
    root = ROOT / 'app/src/main/java'
    if not root.exists():
        note('B2 app/src/main/java NOT FOUND')
        return
    total = 0
    per = []
    for path in root.rglob('*.kt'):
        try:
            text = path.read_text(encoding='utf-8')
        except Exception:
            continue
        c = text.count('SettingScheduledJobs')
        if c > 0:
            total += c
            per.append(path.name + '=' + str(c))
    note('B2 SettingScheduledJobs refs total=' + str(total) + ' files=' + str(len(per)))
    note('B2 | ' + ', '.join(sorted(per)[:20]))


def main():
    patch_reasoning()
    patch_translation()
    dump_strings()
    dump_cron_refs()
    for line in report:
        print('::error::batch243 ' + str(line)[:1500])
    print('::error::batch243 DONE - A1 reasoning regex cache + A2 translation usage '
          '+ B1 strings probe + B2 cron refs probe')


main()