#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch260: 顶部数据源统一（T-M5e）—— TopBar 改纯展示，去掉重复计算

【为什么做这一批】
batch259 只是把 TopBar 里两行从「全局」换成「会话」，TopBar 仍在**自己算**一遍，
与 ChatPageContent 里 batch254 的 `combine(settings, conversation){ getChatModelOf }` 重复。
用户问「最美观吗」——诚实答：不是。本批把它改成**数据源只算一次、TopBar 纯展示**。

【实读到的三处全局读取（都在 ChatPage.kt）】
A. ChatPageContent:
       val assistant = setting.getCurrentAssistant()                      // ← 全局助手
B. ChatPageContent:
       val allowAudioVideoAttachments =
           setting.getCurrentChatModel()?.findProvider(setting.providers) is ProviderSetting.Google   // ← 全局模型
C. TopBar（batch259 改过，但仍是自己算）:
       val assistant = settings.getAssistantOf(conversation) // rhTopModel259
       val model = settings.getChatModelOf(conversation)     // rhTopModel259
       val provider = model?.findProvider(providers = settings.providers, checkOverwrite = false)

【本批改动（5 处，单文件）】
1. ChatPageContent 的 `assistant` 改成会话视角：
       val assistant = setting.getAssistantOf(conversation)
   —— 这会连带 completionProviders（用 assistant.workspaceId）与 ChatFilesPickerSheet（传 assistant）
      都变成会话助手，这是**正确**的：workspaceId 本来就固定在 conversation.config 里。
2. `allowAudioVideoAttachments` 改用 ChatPageContent 已有的 `currentChatModel` 参数（batch254 已是会话级）：
       val allowAudioVideoAttachments = currentChatModel?.findProvider(setting.providers) is ProviderSetting.Google
3. `TopBar` 签名新增 `assistant: Assistant` 与 `currentChatModel: Model?`（插在 settings 之后）。
4. `TopBar` 内部删掉自己算的两行，直接用参数。
5. `TopBar` 调用点补两个实参（assistant / currentChatModel 都已在 ChatPageContent 作用域）。

【为什么不担心 `settings` 参数变多余】
TopBar 里还有 `model?.findProvider(providers = settings.providers, ...)`（改为 currentChatModel 后）
以及可能的状态色/菜单逻辑仍需要 settings，签名里保留。

五查:
 1. import 清单: 需要 `me.rerere.rikkahub.data.model.getAssistantOf`（batch259 已加）；
    `Assistant` / `Model` 的 import 本文件已存在（TopBar/Content 已在用这两个类型）
 2. 同文件冲突: ChatPage.kt 被 batch228/237/238/255/259 改过；
    本批锚点：ChatPageContent 的 assistant 赋值 / allowAudioVideoAttachments 两行 /
    TopBar 签名四行 / TopBar 内两行 / TopBar 调用点四行 —— 五处互不重叠，也都不在 259 的替换点之外
 3. 作用域: assistant 与 currentChatModel 都在 ChatPageContent 内；TopBar 新参数与内部使用点同函数
 4. 括号配对: 唯一变化是 `getCurrentChatModel()` 的外层 `()` 变为 `currentChatModel`，
    => 整文件 balance 预期差 -1/-1（脚本按预期 delta 断言，不是"必须相等"）
 5. 函数签名: 仅 TopBar 增加两个参数（唯一调用点同步补实参）；ChatPageContent 签名不变
Python 三查: Q/SQ 变量构造引号; NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 失败即中止不写盘
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
DIAG = 'ci_diag_batch260.txt'

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
    # 前提：batch259 必须先落地
    if 'rhTopModel259' not in t:
        note('ABORT prerequisite missing: batch259 (rhTopModel259) not applied')
        return

    bal0 = balance(t)
    lines = t.split(NL)

    # ---- 1. ChatPageContent 的 assistant 改会话视角 ----
    a = unique(lines, 'val assistant = setting.getCurrentAssistant()', 'content assistant line')
    lines[a] = ind_of(lines[a]) + 'val assistant = setting.getAssistantOf(conversation) // rhTopModel260'

    # ---- 2. allowAudioVideoAttachments 改用 currentChatModel 参数 ----
    b = unique(lines, 'setting.getCurrentChatModel()?.findProvider(setting.providers) is ProviderSetting.Google',
               'allowAudioVideoAttachments')
    lines[b] = ind_of(lines[b]) + 'currentChatModel?.findProvider(setting.providers) is ProviderSetting.Google // rhTopModel260'

    # ---- 3. TopBar 签名新增两个参数 ----
    c = unique(lines, 'private fun TopBar(', 'TopBar signature')
    if lines[c + 1].strip() != 'hazeState: HazeState,' or lines[c + 2].strip() != 'settings: Settings,':
        note('ABORT TopBar signature shape unexpected: ' + repr(lines[c + 1]) + ' / ' + repr(lines[c + 2]))
        raise Abort('signature shape')
    si = ind_of(lines[c + 2])
    lines[c + 2 + 1:c + 2 + 1] = [
        si + 'assistant: Assistant, // rhTopModel260: 会话视角, 由调用方算好',
        si + 'currentChatModel: Model?, // rhTopModel260',
    ]

    # ---- 4. TopBar 内部改用参数 ----
    d = unique(lines, 'val assistant = settings.getAssistantOf(conversation) // rhTopModel259',
               'topbar assistant line')
    lines[d] = ind_of(lines[d]) + '// rhTopModel260: 直接用参数, 不再重复计算'
    e = unique(lines, 'val model = settings.getChatModelOf(conversation) // rhTopModel259',
               'topbar model line')
    lines[e] = ind_of(lines[e]) + 'val model = currentChatModel'

    # ---- 5. TopBar 调用点补实参 ----
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

    # balance：`getCurrentChatModel()` 的 () 去掉 => 预期 -1/-1
    delta = balance(t2) - bal0
    if delta != -1:
        note('ABORT balance delta unexpected: ' + str(delta) + ' (expected -1)')
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

    # TopBar 内部不应再出现 getChatModelOf / getAssistantOf 调用
    if 'val model = settings.getChatModelOf(conversation)' in t2:
        note('ABORT topbar still computes model')
        raise Abort('stale')

    p.write_text(t2, encoding='utf-8')
    note('ChatPage OK: TopBar pure-presentational, single source of truth (balance delta=-1 as expected)')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch260 diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch260 diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    try:
        patch()
        note('1 topbar pure presentational DONE')
    except Abort as e:
        note('1 topbar pure presentational ABORTED (no file written): ' + str(e))
    except Exception as e:
        note('1 topbar pure presentational EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
    print('::error::batch260 part: topbar pure presentational')
    sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch260 ' + str(line)[:800])
    print('::error::batch260 END lines=' + str(len(report)))


main()