#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch243b: batch243 的修正版 —— 修掉我自己写的方向性断言错误

【batch243 假绿复盘 (76cb148 / run#456)】
表面: Apply patches success / Compile success / R8 success / 两组单测 all tests passed / APK 已发 Release。
事实: 读 snapshot 分支实读证明**零改动落地** ——
  · ChatMessageReasoning.kt: ReasoningContent 内没有 reasoningVisualText        (A1 未落地)
  · TranslationHandler.kt : SHA 与 batch243 推送前完全相同, 无 aiLoggingManager  (A2 未落地)
  · AppModule.kt          : SHA 与 batch243 推送前完全相同, 仍是 TranslationHandler(get())
根因(自查确认, 非猜测): patch_reasoning() 里我加的一条防御性断言方向写反了 ——
    if content_idx >= holder_idx: fail(...)
  真实代码顺序是 holder(声明) 在前、content(使用) 在后:
    val reasoningContent = @Composable {                       <- holder_idx
        MarkdownBlock(
            content = reasoning.reasoning.replaceRegexes(...)  <- content_idx
  于是 holder_idx < content_idx 恒成立 => content_idx >= holder_idx 恒为真 => 无条件 fail() => exit(1)。
  CI 第 7 步把 exit(1) sed 成 exit(0), 脚本静默停在第一部分, A2/B1/B2 全部未执行。
教训: "加了防御性断言"不等于"断言方向正确"; 断言本身也要被验证。
      而假绿只能靠读 snapshot(CI 推送的 patch 后源码树)抓出来, job conclusion 抓不出来。

【本版修正】
  1. 删除方向写反的断言, 改为正确方向(holder_idx 必须 < content_idx), 注释里写明真实顺序。
  2. 每个独立部分放进自己的 try, 捕获 SystemExit 与 Exception, 失败记录后继续。
     理由: warn-only 环境已让 fail-loud 失效(exit 被吞), 继续执行才能让一次 run 拿到最多落地与最多诊断。
     每次写入前仍保留 balance 前后断言, 不会写入括号不平衡的代码。
  3. A2 采用两阶段提交: 先只读校验 TranslationHandler 与 AppModule 两侧锚点全部成立, 再依次写盘。
     否则单侧写盘会造成"构造要 2 个参数、DI 只传 1 个"的编译红。
  4. 取证双通道: ::error 汇总 + 写 ci_diag_batch243b.txt 到仓库根目录
     (随 Snapshot patched sources 步骤进 snapshot 分支), 绕开 annotation 配额与截断。

五查:
  1. import 清单: 三处改动零新增 import
     (ChatMessageReasoning.kt 的 remember 已 import; TranslationHandler 与 AILoggingManager 同包;
      AppModule 已 import AILoggingManager)
  2. 同文件冲突: ChatMessageReasoning/TranslationHandler/AppModule 均无在链 patch 触碰;
     不碰 batch92 改过的四个文件(GenerationHandler/AILogging/PreferencesStore/SettingProviderPage)
  3. 作用域: reasoningVisualText 插在 ReasoningContent 内, reasoning/assistant 同作用域;
     aiLoggingManager 为类成员
  4. 括号配对: 逐文件断言修改前后 balance 完全一致
  5. 函数签名: 仅 TranslationHandler 主构造增加一个参数, 唯一注入点同步更新
Python 三查: Q/SQ 变量构造引号; NL 显式 concat 禁 join/f-string/walrus;
helper 先定义后用; 锚点行级 strip 匹配; 失败 ::error + 记录后继续(不静默)
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
SQ = chr(39)
MARK = 'rhBatch243'

REASONING = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageReasoning.kt'
TRANSLATION = 'app/src/main/java/me/rerere/rikkahub/data/ai/TranslationHandler.kt'
APPMODULE = 'app/src/main/java/me/rerere/rikkahub/di/AppModule.kt'
STRINGS_ZH = 'app/src/main/res/values-zh/strings.xml'
STRINGS_EN = 'app/src/main/res/values/strings.xml'
DIAG = 'ci_diag_batch243b.txt'

report = []


class AnchorMiss(Exception):
    pass


def fail(msg):
    print('::error::batch243b ' + str(msg)[:1500])
    sys.stdout.flush()
    raise AnchorMiss(str(msg))


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


def run_part(name, fn):
    try:
        fn()
        report.append(name + ': OK')
    except AnchorMiss as e:
        report.append(name + ': ANCHOR-MISS ' + str(e)[:300])
    except SystemExit as e:
        report.append(name + ': EXIT ' + str(getattr(e, 'code', '?')))
    except Exception as e:
        report.append(name + ': EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
    print('::error::batch243b part ' + report[-1][:900])
    sys.stdout.flush()


# ===========================================================================
# A1. ChatMessageReasoning.kt —— reasoning 全文正则改 remember 缓存
# ===========================================================================
def part_reasoning():
    p = ROOT / REASONING
    if not p.exists():
        fail('ChatMessageReasoning.kt missing')
    t = p.read_text(encoding='utf-8')
    if 'rhReasoningRegCache243' in t:
        report.append('A1 already applied (marker present)')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    content_idx = find_line(lines, 'content = reasoning.reasoning.replaceRegexes(',
                            'reasoning replaceRegexes call')
    holder_idx = find_line(lines, 'val reasoningContent = @Composable {',
                           'reasoningContent holder')

    # 真实顺序: holder(声明) 在前, content(使用) 在后 => 必须 holder_idx < content_idx
    if holder_idx > content_idx:
        fail('reasoning: unexpected layout holder=' + str(holder_idx)
             + ' content=' + str(content_idx) + ' (holder must precede content)')

    expect = [
        'assistant = assistant,',
        'scope = AssistantAffectScope.ASSISTANT,',
        'visual = true,',
        '),',
    ]
    for off, want in enumerate(expect):
        got = lines[content_idx + 1 + off].strip()
        if got != want:
            fail('reasoning: line ' + str(off + 1) + ' expected ' + repr(want) + ' got ' + repr(got))

    ci = ind_of(lines[content_idx])
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

    lines = lines[:content_idx] + [ci + 'content = reasoningVisualText,'] + lines[content_idx + 5:]
    holder_idx2 = find_line(lines, 'val reasoningContent = @Composable {', 'holder after edit')
    lines = lines[:holder_idx2] + pre + lines[holder_idx2:]

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        fail('reasoning: balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
    if 'content = reasoning.reasoning.replaceRegexes(' in t2:
        fail('reasoning: old inline call still present')
    if 'val reasoningVisualText = remember(' not in t2:
        fail('reasoning: cache holder missing')
    if t2.count('reasoning.reasoning.replaceRegexes(') != 1:
        fail('reasoning: replaceRegexes count=' + str(t2.count('reasoning.reasoning.replaceRegexes(')))
    if 'content = reasoningVisualText,' not in t2:
        fail('reasoning: MarkdownBlock content not rewired')
    p.write_text(t2, encoding='utf-8')
    report.append('A1 wrote ChatMessageReasoning.kt')


# ===========================================================================
# A2. TranslationHandler.kt + AppModule.kt —— 翻译场景打点(两阶段提交)
# ===========================================================================
def part_translation():
    tp = ROOT / TRANSLATION
    ap = ROOT / APPMODULE
    if not tp.exists():
        fail('TranslationHandler.kt missing')
    if not ap.exists():
        fail('AppModule.kt missing')

    tt = tp.read_text(encoding='utf-8')
    if 'rhTranslateUsageT9' in tt:
        report.append('A2 already applied (marker present)')
        return

    tlines = tt.split(NL)
    alines = ap.read_text(encoding='utf-8').split(NL)

    # ---- 阶段 1: 只读校验两侧锚点, 全部成立才写盘 ----
    ctor_idx = find_line(tlines, 'private val providerManager: ProviderManager,',
                         'TranslationHandler ctor param')
    handler_idx = find_line(tlines, 'val providerHandler = providerManager.getProviderByType(provider)',
                            'TranslationHandler providerHandler line')
    di_idx = find_line(alines, 'single { TranslationHandler(get()) }',
                       'AppModule TranslationHandler single')
    if di_idx < ctor_idx and di_idx < 0:
        fail('unreachable')
    if 'import me.rerere.rikkahub.data.ai.AILoggingManager' not in ap.read_text(encoding='utf-8'):
        fail('AppModule: AILoggingManager import missing (explicit get<T>() needs it)')

    bal_t0 = balance(tt)
    bal_a0 = balance(lines_to_text(alines))

    # ---- 阶段 2: 两侧都验证通过后依次写盘 ----
    ti = ind_of(tlines[ctor_idx])
    tlines = tlines[:ctor_idx + 1] + [ti + 'private val aiLoggingManager: AILoggingManager, // rhTranslateUsageT9'] + tlines[ctor_idx + 1:]
    handler_idx2 = find_line(tlines, 'val providerHandler = providerManager.getProviderByType(provider)',
                             'TranslationHandler providerHandler after ctor edit')
    hi = ind_of(tlines[handler_idx2])
    tlines = tlines[:handler_idx2 + 1] + [hi + 'aiLoggingManager.recordProviderUsed(provider.id) // rhTranslateUsageT9'] + tlines[handler_idx2 + 1:]

    t2 = lines_to_text(tlines)
    if balance(t2) != bal_t0:
        fail('translation: balance changed ' + str(bal_t0) + ' -> ' + str(balance(t2)))
    for need in ['private val aiLoggingManager: AILoggingManager,',
                 'aiLoggingManager.recordProviderUsed(provider.id)']:
        if need not in t2:
            fail('translation: selfcheck missing ' + need)
    if t2.count('recordProviderUsed') != 1:
        fail('translation: recordProviderUsed count=' + str(t2.count('recordProviderUsed')))
    tp.write_text(t2, encoding='utf-8')

    di = ind_of(alines[di_idx])
    alines[di_idx] = di + 'single { TranslationHandler(get(), get<AILoggingManager>()) } // rhTranslateUsageT9'
    a2 = lines_to_text(alines)
    if balance(a2) != bal_a0:
        fail('appmodule: balance changed ' + str(bal_a0) + ' -> ' + str(balance(a2)))
    if 'TranslationHandler(get(), get<AILoggingManager>())' not in a2:
        fail('appmodule: wiring missing')
    if a2.count('TranslationHandler(get())') != 0:
        fail('appmodule: old wiring still present')
    ap.write_text(a2, encoding='utf-8')
    report.append('A2 wrote TranslationHandler.kt + AppModule.kt')


# ===========================================================================
# B1. #9 LITE / 转文件 文案取证(只读)
# ===========================================================================
def part_strings():
    keys = ['转文件', '转成文件', '存为文件', '存成文件', '保存为文件', '转为文件', 'LITE', 'Lite']
    for rel in [STRINGS_ZH, STRINGS_EN]:
        p = ROOT / rel
        if not p.exists():
            report.append('B1 ' + rel + ' NOT FOUND')
            continue
        text = p.read_text(encoding='utf-8')
        hits = []
        for i, line in enumerate(text.split(NL)):
            s = line.strip()
            if not s.startswith('<string'):
                continue
            for k in keys:
                if k in s:
                    hits.append('L' + str(i + 1) + ' :: ' + s[:220])
                    break
        report.append('B1 ' + rel + ' hits=' + str(len(hits)))
        for h in hits[:16]:
            report.append('B1 ' + h)


# ===========================================================================
# B2. #6 SettingScheduledJobs 引用统计(只读)
# ===========================================================================
def part_cron():
    root = ROOT / 'app/src/main/java'
    if not root.exists():
        report.append('B2 app/src/main/java NOT FOUND')
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
    report.append('B2 SettingScheduledJobs refs total=' + str(total) + ' files=' + str(len(per)))
    report.append('B2 ' + ', '.join(sorted(per)[:24]))


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch243b diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch243b diag write failed ' + str(e)[:200])
    sys.stdout.flush()


def main():
    run_part('A1 reasoning regex cache', part_reasoning)
    run_part('A2 translation usage + DI', part_translation)
    run_part('B1 strings probe', part_strings)
    run_part('B2 cron refs probe', part_cron)
    write_diag()
    for line in report:
        print('::error::batch243b ' + str(line)[:1500])
    print('::error::batch243b DONE parts=' + str(len(report)))


main()