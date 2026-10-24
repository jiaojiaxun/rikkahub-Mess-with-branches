#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch260b: 修 batch260 的 balance 预期算错（ABORT delta 0，正确预期是 -3）

【batch260 为什么中止了（诚实复盘）】
ci_diag_batch260.txt: `ABORT balance delta unexpected: 0 (expected -1)`

我断言的 expected delta 是 -1，但实际算错。逐处重算：
  改动1 ChatPageContent `getCurrentAssistant()` → `getAssistantOf(conversation)`：1 对 → 1 对，delta 0
  改动2 ChatPageContent `setting.getCurrentChatModel()?.findProvider(...)` → `currentChatModel?.findProvider(...)`：
        2 对 → 1 对，delta -1
  改动3 TopBar 签名加两个参数行：0 对
  改动4 TopBar 内部删掉两行自算（`settings.getAssistantOf(conversation)` 和 `settings.getChatModelOf(conversation)`）：
        各删 1 对，共 -2
  改动5 调用点补两个实参行：0 对
  => 总 delta = -1 + -2 = **-3**，不是 -1。

我上一轮只算了改动2，漏算了改动4（TopBar 里那两行 `()` 被删掉）。这是纯算术错，不是逻辑错。

【本批唯一修正】expected balance delta 从 -1 改为 -3，其余代码与 batch260 完全相同。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
DIAG = 'ci_diag_batch260b.txt'

PAGE = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'

report = []


def note(msg):
    report.append(str(msg)[:900])


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


class Abort(Exception):
    pass


def unique(lines, needle, label):
    hits = [i for i, ln in enumerate(lines) if ln.strip() == needle]
    if len(hits) != 1:
        note('ABORT ' + label + ': count=' + str(len(hits)) + ' (need 1) -> ' + repr(needle))
        raise Abort(label)
    return hits[0]


def patch():
    p = ROOT / PAGE
    if not p.exists():
        note('ABORT missing ChatPage.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhTopModel260' in t:
        note('already applied')
        return
    if 'rhTopModel259' not in t:
        note('ABORT prerequisite missing: batch259 (rhTopModel259) not applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    a = unique(lines, 'val assistant = setting.getCurrentAssistant()', 'content assistant line')
    lines[a] = ind_of(lines[a]) + 'val assistant = setting.getAssistantOf(conversation) // rhTopModel260'

    b = unique(lines, 'setting.getCurrentChatModel()?.findProvider(setting.providers) is ProviderSetting.Google',
               'allowAudioVideoAttachments')
    lines[b] = ind_of(lines[b]) + 'currentChatModel?.findProvider(setting.providers) is ProviderSetting.Google // rhTopModel260'

    c = unique(lines, 'private fun TopBar(', 'TopBar signature')
    if lines[c + 1].strip() != 'hazeState: HazeState,' or lines[c + 2].strip() != 'settings: Settings,':
        note('ABORT TopBar signature shape unexpected: ' + repr(lines[c + 1]) + ' / ' + repr(lines[c + 2]))
        raise Abort('signature shape')
    si = ind_of(lines[c + 2])
    lines[c + 2 + 1:c + 2 + 1] = [
        si + 'assistant: Assistant, // rhTopModel260: 会话视角, 由调用方算好',
        si + 'currentChatModel: Model?, // rhTopModel260',
    ]

    d = unique(lines, 'val assistant = settings.getAssistantOf(conversation) // rhTopModel259',
               'topbar assistant line')
    lines[d] = ind_of(lines[d]) + '// rhTopModel260: 直接用参数, 不再重复计算'
    e = unique(lines, 'val model = settings.getChatModelOf(conversation) // rhTopModel259',
               'topbar model line')
    lines[e] = ind_of(lines[e]) + 'val model = currentChatModel'

    f = unique(lines, 'TopBar(', 'TopBar call')
    if lines[f + 1].strip() != 'hazeState = hazeState,' or lines[f + 2].strip() != 'settings = setting,':
        note('ABORT TopBar call shape unexpected: ' + repr(lines[f + 1]) + ' / ' + repr(lines[f + 2]))
        raise Abort('call shape')
    ci = ind_of(lines[f + 2])
    lines[f + 3:f + 3] = [
        ci + 'assistant = assistant, // rhTopModel260',
        ci + 'currentChatModel = currentChatModel, // rhTopModel260',
    ]

    t2 = lines_to_text(lines)

    # 修正：总 delta = 改动2(-1) + 改动4(-2) = -3
    delta = balance(t2) - bal0
    if delta != -3:
        note('ABORT balance delta unexpected: ' + str(delta) + ' (expected -3)')
        raise Abort('balance')

    for need in ['val assistant = setting.getAssistantOf(conversation) // rhTopModel260',
                 'currentChatModel?.findProvider(setting.providers) is ProviderSetting.Google',
                 'assistant: Assistant, // rhTopModel260',
                 'currentChatModel: Model?, // rhTopModel260',
                 'val model = currentChatModel',
                 'assistant = assistant, // rhTopModel260',
                 'currentChatModel = currentChatModel, // rhTopModel260']:
        if need not in t2:
            note('ABORT selfcheck missing ' + need)
            raise Abort('selfcheck')

    if t2.count('rhTopModel260') < 7:
        note('ABORT marker count=' + str(t2.count('rhTopModel260')))
        raise Abort('marker')

    if 'val model = settings.getChatModelOf(conversation)' in t2:
        note('ABORT topbar still computes model')
        raise Abort('stale')

    p.write_text(t2, encoding='utf-8')
    note('ChatPage OK: TopBar pure-presentational, single source of truth (balance delta=-3 as expected)')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch260b diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch260b diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    try:
        patch()
        note('1 topbar pure presentational DONE')
    except Abort as e:
        note('1 topbar pure presentational ABORTED (no file written): ' + str(e))
    except Exception as e:
        note('1 topbar pure presentational EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
    print('::error::batch260b part: topbar pure presentational')
    sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch260b ' + str(line)[:800])
    print('::error::batch260b END lines=' + str(len(report)))


main()