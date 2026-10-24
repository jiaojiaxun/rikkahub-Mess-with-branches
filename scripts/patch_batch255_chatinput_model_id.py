#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch255: 输入栏模型选择器读助手级 id（A3/A4 的第二处漏改）—— 改读会话 config

【现象】用户实测 run463：打开输入栏后选模型「不行」。
【batch254 已修】ChatVM.currentChatModel 改走 getChatModelOf(conversation)（已实证落地）。

【本批修的第二处（实读确认，不是推断）】
ChatInput.kt 内部的模型选择器:
    ModelSelector(
        modelId = assistant.chatModelId ?: settings.chatModelId,   // ← 助手级
        providers = settings.providers,
        onSelect = { onUpdateChatModel(it) },
        ...
    )
而 ChatInput 里的 assistant 来自:
    val assistant = settings.getCurrentAssistant()                 // ← 全局当前助手

调用方 ChatPage 的写入回调:
    onUpdateChatModel = { vm.setChatModel(assistant = setting.getCurrentAssistant(), model = it) }
    -> chatService.setConversationModel(_conversationId, model.id)   // 写的是会话 config

=> 写：会话 config.chatModelId；读：assistant.chatModelId（助手级，永远不变）
   => 输入栏的模型按钮高亮/名字永远停在旧模型，用户当然觉得「切不了」。
   这是 A3/A4 的典型半边改：ChatService 内部读链改了、ChatVM 显示源改了(254)、
   但 ChatInput 的 ModelSelector 仍然读助手。

【修法（三处，跨两个文件）】
1. ChatInput 签名新增 `conversationChatModelId: Uuid? = null`（带默认值，其余调用方零改动）
   + import kotlin.uuid.Uuid
2. ModelSelector 的 modelId 改为:
       conversationChatModelId ?: assistant.chatModelId ?: settings.chatModelId
   （会话有 config 用会话的；新会话无 config 回退助手；助手也没设回退全局）
3. ChatPage 调用 ChatInput 时传 `conversationChatModelId = conversation.config?.chatModelId`

【本批不改（记录在案）】
ChatInput 里还有两处读全局模型:
    val chatModel = settings.getCurrentChatModel()   (SearchPickerButton 用)
    val model = settings.getCurrentChatModel()       (Reasoning 按钮的 REASONING 能力判断)
它们只影响「搜索/推理按钮是否显示」，不影响模型选择结果；且改动要连带 ChatInput 内部
能力判断链，风险高于收益，留下一批单独评估。

五查:
 1. import 清单: ChatInput.kt 需新增 1 条 kotlin.uuid.Uuid（当前未 import）；
    ChatPage.kt 零新增（conversation 与 config 都在作用域，Uuid 已由其传递链覆盖）
 2. 同文件冲突: ChatInput.kt 无在链批次改动；ChatPage.kt 被 batch228(PlanBar)/237/238 改过，
    本批锚点是 ChatInput( 调用处的 settings = setting, 一行，与上述落点不重叠
 3. 作用域: conversationChatModelId 有默认值 => 现有调用方（若有其它入口）无需改动；
    ChatPage 的 conversation 在 ChatPageContent 参数内
 4. 括号配对: 三处均为「无括号变化的表达式/参数插入」=> 整文件 balance 不变（脚本断言）
 5. 函数签名: ChatInput 增加一个带默认值的参数（向后兼容）；ModelSelector 签名不动
Python 三查: Q/SQ 变量构造引号; NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 失败记录并继续
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
DIAG = 'ci_diag_batch255.txt'

CHATINPUT = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ChatInput.kt'
CHATPAGE = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'

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


def find_idx(lines, needle, label):
    hits = [i for i, ln in enumerate(lines) if ln.strip() == needle]
    if len(hits) == 0:
        note('ANCHOR-MISS ' + label + ' -> ' + repr(needle))
        raise RuntimeError('anchor miss ' + label)
    if len(hits) != 1:
        note('ANCHOR-DUP ' + label + ' count=' + str(len(hits)))
        raise RuntimeError('anchor dup ' + label)
    return hits[0]


def patch_chat_input():
    p = ROOT / CHATINPUT
    if not p.exists():
        note('MISSING ChatInput.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhConvModel255' in t:
        note('chatinput already applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    # 1. import Uuid
    if 'import kotlin.uuid.Uuid' not in t:
        a = find_idx(lines, 'import kotlin.time.Duration.Companion.seconds', 'Uuid import anchor')
        lines = lines[:a + 1] + ['import kotlin.uuid.Uuid // rhConvModel255'] + lines[a + 1:]

    # 2. 签名新增参数（插在 onUpdateChatModel 之前，保持语义相邻）
    b = find_idx(lines, 'onUpdateChatModel: (Model) -> Unit,', 'onUpdateChatModel param')
    bi = ind_of(lines[b])
    lines = lines[:b] + [
        bi + '// rhConvModel255: 会话级模型 id —— 输入栏的选择器必须显示会话真正的模型',
        bi + 'conversationChatModelId: Uuid? = null,',
    ] + lines[b:]

    # 3. ModelSelector 的 modelId 改会话级优先
    c = find_idx(lines, 'modelId = assistant.chatModelId ?: settings.chatModelId,', 'ModelSelector modelId')
    ci = ind_of(lines[c])
    lines[c] = ci + 'modelId = conversationChatModelId ?: assistant.chatModelId ?: settings.chatModelId, // rhConvModel255'

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('chatinput balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        return
    for need in ['import kotlin.uuid.Uuid',
                 'conversationChatModelId: Uuid? = null,',
                 'modelId = conversationChatModelId ?: assistant.chatModelId ?: settings.chatModelId,']:
        if need not in t2:
            note('chatinput selfcheck missing ' + need)
            return
    p.write_text(t2, encoding='utf-8')
    note('chatinput OK: ModelSelector reads session model id first')


def patch_chat_page():
    p = ROOT / CHATPAGE
    if not p.exists():
        note('MISSING ChatPage.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhConvModel255' in t:
        note('chatpage already applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    a = find_idx(lines, 'onUpdateChatModel = {', 'ChatPage onUpdateChatModel arg')
    ai = ind_of(lines[a])
    lines = lines[:a] + [
        ai + '// rhConvModel255: 把会话级模型 id 传进输入栏，选择器才会显示会话真实模型',
        ai + 'conversationChatModelId = conversation.config?.chatModelId,',
    ] + lines[a:]

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('chatpage balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        return
    if 'conversationChatModelId = conversation.config?.chatModelId,' not in t2:
        note('chatpage selfcheck missing arg')
        return
    p.write_text(t2, encoding='utf-8')
    note('chatpage OK: passes conversation.config.chatModelId')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch255 diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch255 diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    for name, fn in [
        ('1 ChatInput ModelSelector session id', patch_chat_input),
        ('2 ChatPage pass conversation model id', patch_chat_page),
    ]:
        try:
            fn()
            note(name + ' DONE')
        except Exception as e:
            note(name + ' EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
        print('::error::batch255 part: ' + name)
        sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch255 ' + str(line)[:800])
    print('::error::batch255 END lines=' + str(len(report)))


main()