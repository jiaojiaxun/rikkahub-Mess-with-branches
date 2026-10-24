#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch259: 聊天页顶部模型名不跟随会话（A3/A4 的第四处漏改）

【现象】用户实测 run477：模型切换后，聊天页**顶部**显示的模型/provider 不跟着变。
（输入栏那个选择器已在 batch255 修好；这是顶部标题下方那行小字。）

【根因（实读 ChatPage.kt 的 TopBar）】
    title = {
        Surface(...) {
            Column {
                val assistant = settings.getCurrentAssistant()      // ← 全局当前助手
                val model = settings.getCurrentChatModel()          // ← 全局当前模型
                val provider = model?.findProvider(providers = settings.providers, checkOverwrite = false)
                Text(text = conversation.title...)
                if (model != null && provider != null) {
                    Text(text = "${assistant.name} / ${model.displayName} (${provider.name})", ...)
                }
            }
        }
    }
=> 顶部完全没看 `conversation.config`，所以 A3/A4 把写入改成会话级之后，
   顶部这行小字永远停在"全局当前助手 + 全局当前模型"。
   TopBar 的签名里**已经有 conversation 参数**，所以零签名改动即可修。

【修法（两行 + 两条 import）】
    val assistant = settings.getAssistantOf(conversation)   // 会话视角的助手
    val model = settings.getChatModelOf(conversation)       // 会话固定的模型（被删则回退助手模型）
两者都在 `me.rerere.rikkahub.data.model.ConversationConfig.kt` 里定义，语义已实读确认：
· getAssistantOf：用 conversation.config 覆盖助手字段 + 过滤失效的 mcp/mode/lorebook 引用
· getChatModelOf：config.chatModelId 优先；模型被删回退助手当前模型；内置搜索跟随该模型开关

【这是 A3/A4「半边改」的第四处，完整清单】
 1. ChatVM.currentChatModel            → batch254 已改 combine(settings, conversation)
 2. ChatInput 的 ModelSelector          → batch255 已改 conversationChatModelId 优先
 3. TopBar 顶部模型/provider 小字        → 本批
 4. ChatInput 的 SearchPickerButton / ReasoningButton 能力判断 → 未改（只影响按钮是否显示）

五查:
 1. import 清单: 需新增 `me.rerere.rikkahub.data.model.getAssistantOf` 与 `getChatModelOf`；
    两条都必须找到唯一锚点，否则**中止且不写盘**
 2. 同文件冲突: ChatPage.kt 被 batch228(PlanBar)/237/238/255 改过；
    本批锚点是 TopBar title 里的「assistant + model 两行连续赋值」，与上述落点不重叠
 3. 作用域: TopBar 已有 settings 与 conversation 参数，两行替换不改变作用域
 4. 括号配对: 两行均为 `settings.xxx()` 调用，括号 1 对 1 => balance 不变（断言）
 5. 函数签名: 零改动（TopBar 参数不动）
Python 三查: Q/SQ 变量构造引号; NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 失败即中止
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
DIAG = 'ci_diag_batch259.txt'

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
    if 'rhTopModel259' in t:
        note('already applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    # A. 先定位两行连续赋值（唯一窗口），失败即中止
    anchor = -1
    for i in range(len(lines) - 1):
        if lines[i].strip() == 'val assistant = settings.getCurrentAssistant()' and \
                lines[i + 1].strip() == 'val model = settings.getCurrentChatModel()':
            if anchor >= 0:
                note('ABORT ambiguous assistant+model window at ' + str(anchor) + ' and ' + str(i))
                raise Abort('ambiguous window')
            anchor = i
    if anchor < 0:
        note('ABORT assistant+model window not found')
        raise Abort('window missing')

    # B. 再确认两条 import 的锚点（先查存在性，缺一个就中止）
    has_assistant_of = 'import me.rerere.rikkahub.data.model.getAssistantOf' in t
    has_chat_model_of = 'import me.rerere.rikkahub.data.model.getChatModelOf' in t
    model_anchor_line = 'import me.rerere.rikkahub.data.model.Conversation'
    if not has_assistant_of or not has_chat_model_of:
        if model_anchor_line not in t:
            note('ABORT import anchor missing: ' + model_anchor_line)
            raise Abort('import anchor')

    # C. 全部确认后才动
    ind = ind_of(lines[anchor])
    lines[anchor] = ind + 'val assistant = settings.getAssistantOf(conversation) // rhTopModel259'
    lines[anchor + 1] = ind + 'val model = settings.getChatModelOf(conversation) // rhTopModel259'

    if not has_chat_model_of or not has_assistant_of:
        idx = unique(lines, model_anchor_line, 'import Conversation anchor')
        add = []
        if not has_assistant_of:
            add.append('import me.rerere.rikkahub.data.model.getAssistantOf // rhTopModel259')
        if not has_chat_model_of:
            add.append('import me.rerere.rikkahub.data.model.getChatModelOf // rhTopModel259')
        lines = lines[:idx + 1] + add + lines[idx + 1:]

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('ABORT balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        raise Abort('balance')

    for need in ['val assistant = settings.getAssistantOf(conversation)',
                 'val model = settings.getChatModelOf(conversation)',
                 'import me.rerere.rikkahub.data.model.getAssistantOf',
                 'import me.rerere.rikkahub.data.model.getChatModelOf']:
        if need not in t2:
            note('ABORT selfcheck missing ' + need)
            raise Abort('selfcheck')

    if t2.count('rhTopModel259') < 2:
        note('ABORT marker count too low')
        raise Abort('marker')

    # 顶部不应再有全局取模型
    if 'val model = settings.getCurrentChatModel()' in t2:
        note('ABORT old global model read still present')
        raise Abort('stale')

    p.write_text(t2, encoding='utf-8')
    note('ChatPage OK: TopBar uses getAssistantOf/getChatModelOf(conversation)')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch259 diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch259 diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    try:
        patch()
        note('1 top bar model DONE')
    except Abort as e:
        note('1 top bar model ABORTED (no file written): ' + str(e))
    except Exception as e:
        note('1 top bar model EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
    print('::error::batch259 part: top bar model')
    sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch259 ' + str(line)[:800])
    print('::error::batch259 END lines=' + str(len(report)))


main()