#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch254: 模型切换「看不到变化」修复（ChatVM.currentChatModel 仍读全局）+ 输入栏模型选择取证

【现象】用户实测 run463：模型切换不了；打开输入栏后选模型也不生效。

【根因（已实读确认，不是猜）】
A3(batch232) 把 **ChatService 内部**的解析链改成了会话级：
    settings.getAssistantOf(conversation) / settings.getChatModelOf(conversation)
A4(batch234) 把**写入侧**改成会话级：ChatVM.setChatModel -> chatService.setConversationModel
                        -> 改 conversation.config.chatModelId -> updateConversation + 落库 config 列。
但 ChatVM 里给 UI 用的显示源**没跟着改**：
    // 当前模型
    val currentChatModel = settings.map { settings ->
        settings.getCurrentChatModel()          // ← 读的是全局助手模型，不是会话 config
    }.stateIn(viewModelScope, SharingStarted.Lazily, null)
=> 写入落到会话 config 了（发送时 ChatService 用的确实是新模型），
   但顶部/输入栏显示的那颗「当前模型」永远来自 settings.getCurrentChatModel()，
   切完 UI 纹丝不动 => 用户感知为「切换不了」。
   这是典型的 A3/A4 只改了半边：读链(服务端)改了，读链(UI 端)漏改。

修法：currentChatModel 改成 combine(settings, conversation)，用会话级解析：
    val currentChatModel = combine(settings, conversation) { s, c -> s.getChatModelOf(c) }
        .stateIn(viewModelScope, SharingStarted.Lazily, null)
getChatModelOf 的语义已在 ConversationConfig.kt 实读确认：
    config 存在且模型未删 => 用 config.chatModelId；被删 => 回退助手当前模型。
新 import：kotlinx.coroutines.flow.combine、me.rerere.rikkahub.data.model.getChatModelOf。

【同批取证（只读，下一批用）】
1. ChatPage.kt 里 setChatModel / currentChatModel / 模型选择面板的引用行
   —— 确认输入栏的模型入口读的是哪个值（若它直接用 assistant.chatModelId，也要一起改）。
2. ImportedDatabaseReconciler.kt 的 MemoryEntity 段（L100-140）
   —— batch252 已确认它是**结构协调器**（CREATE TABLE / INDEX / workspaces_new 重建），
      不做 assistant_id 重映射，所以 T-M4「记忆挂在旧助手 id 下」的假设也需再验。
3. MemoryRepository.getMemoriesOfAssistant 的调用方（AssistantDetailVM 的 memories 来源），
   确认记忆页到底查「当前助手」还是「会话的助手」——这决定旧备份恢复后能不能显示。

五查:
 1. import 清单: ChatVM 需新增 2 条（combine、getChatModelOf），均为本文件尚未 import 的符号
 2. 同文件冲突: ChatVM.kt 被 batch234(A4 setChatModel)、batch250(引用队列) 改过；
    本批锚点是 currentChatModel 的 settings.map 块，与上述两处不重叠
 3. 作用域: settings 与 conversation 都是 ChatVM 的 val（StateFlow），combine 在 init 之外合法
 4. 括号配对: 旧块 map{} 与新块 combine(settings, conversation){} 各 1 对括号 + 1 对花括号，
    原块还有 getCurrentChatModel() 1 对 => 两版均自配平 => 整文件 balance 不变（断言）
 5. 函数签名: 零改动（只换属性初始化表达式）
Python 三查: Q/SQ 变量构造引号; NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 失败记录并继续
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
DIAG = 'ci_diag_batch254.txt'

CHATVM = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatVM.kt'
CHATPAGE = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'
RECONCILER = 'app/src/main/java/me/rerere/rikkahub/data/db/ImportedDatabaseReconciler.kt'
DETAILVM = 'app/src/main/java/me/rerere/rikkahub/ui/pages/assistant/detail/AssistantDetailVM.kt'

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


def find_idx(lines, needle, label):
    hits = [i for i, ln in enumerate(lines) if ln.strip() == needle]
    if len(hits) == 0:
        note('ANCHOR-MISS ' + label + ' -> ' + repr(needle))
        raise RuntimeError('anchor miss ' + label)
    if len(hits) != 1:
        note('ANCHOR-DUP ' + label + ' count=' + str(len(hits)))
        raise RuntimeError('anchor dup ' + label)
    return hits[0]


def patch_current_model():
    p = ROOT / CHATVM
    if not p.exists():
        note('MISSING ChatVM.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhSessionModel254' in t:
        note('chatvm already applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    # 1. 旧块替换
    i = find_idx(lines, 'val currentChatModel = settings.map { settings ->', 'currentChatModel map head')
    expect = ['settings.getCurrentChatModel()', '}.stateIn(viewModelScope, SharingStarted.Lazily, null)']
    got = [ln.strip() for ln in lines[i + 1:i + 1 + len(expect)]]
    if got != expect:
        note('currentChatModel body mismatch got=' + repr(got))
        return
    repl = [
        '// rhSessionModel254: 显示源必须走会话级解析，否则 A3/A4 改了写入与发送、UI 却永远显示全局助手模型',
        'val currentChatModel = combine(settings, conversation) { s, c ->',
        '    s.getChatModelOf(c)',
        '}.stateIn(viewModelScope, SharingStarted.Lazily, null)',
    ]
    lines = lines[:i] + repl + lines[i + 1 + len(expect):]

    # 2. import combine
    if 'import kotlinx.coroutines.flow.combine' not in lines_to_text(lines):
        a = find_idx(lines, 'import kotlinx.coroutines.flow.distinctUntilChanged', 'combine import anchor')
        lines = lines[:a] + ['import kotlinx.coroutines.flow.combine'] + lines[a:]

    # 3. import getChatModelOf
    if 'import me.rerere.rikkahub.data.model.getChatModelOf' not in lines_to_text(lines):
        b = find_idx(lines, 'import me.rerere.rikkahub.data.model.Conversation', 'getChatModelOf import anchor')
        lines = lines[:b + 1] + ['import me.rerere.rikkahub.data.model.getChatModelOf // rhSessionModel254'] + lines[b + 1:]

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('chatvm balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        return
    for need in ['import kotlinx.coroutines.flow.combine',
                 'import me.rerere.rikkahub.data.model.getChatModelOf',
                 'val currentChatModel = combine(settings, conversation) { s, c ->',
                 's.getChatModelOf(c)']:
        if need not in t2:
            note('chatvm selfcheck missing ' + need)
            return
    if 'settings.getCurrentChatModel()' in t2.split('rhSessionModel254')[1]:
        note('chatvm old getCurrentChatModel still present after marker')
        return
    p.write_text(t2, encoding='utf-8')
    note('chatvm OK: currentChatModel -> getChatModelOf(conversation)')


def probe_chat_page():
    p = ROOT / CHATPAGE
    if not p.exists():
        note('probe missing ChatPage.kt')
        return
    lines = p.read_text(encoding='utf-8').split(NL)
    keys = ['setChatModel', 'currentChatModel', 'chatModelId', 'ModelPicker', 'ModelSelector',
            'getChatModelOf', 'assistant.chatModelId']
    hits = []
    for i, ln in enumerate(lines):
        s = ln.strip()
        for k in keys:
            if k in s:
                hits.append('L' + str(i + 1) + ':' + s[:170])
                break
    note('probe ChatPage hits=' + str(len(hits)))
    for h in hits[:44]:
        note('page ' + h)


def probe_memory_chain():
    p = ROOT / RECONCILER
    if p.exists():
        lines = p.read_text(encoding='utf-8').split(NL)
        seg = []
        for i, ln in enumerate(lines):
            s = ln.strip()
            if 95 <= i + 1 <= 140 and s:
                seg.append('L' + str(i + 1) + ':' + s[:180])
        note('reconciler L95-140 lines=' + str(len(seg)))
        for s in seg:
            note('rec ' + s)

    p = ROOT / DETAILVM
    if not p.exists():
        note('probe missing AssistantDetailVM.kt')
        return
    lines = p.read_text(encoding='utf-8').split(NL)
    keys = ['memories', 'getMemoriesOfAssistant', 'getGlobalMemories', 'getSessionMemories',
            'enableShortMemory', 'useGlobalMemory', 'assistantId']
    hits = []
    for i, ln in enumerate(lines):
        s = ln.strip()
        for k in keys:
            if k in s:
                hits.append('L' + str(i + 1) + ':' + s[:170])
                break
    note('probe AssistantDetailVM memories hits=' + str(len(hits)))
    for h in hits[:40]:
        note('dvm ' + h)


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch254 diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch254 diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    for name, fn in [
        ('1 currentChatModel -> session scope', patch_current_model),
        ('2 ChatPage model entry probe', probe_chat_page),
        ('3 memory chain probe', probe_memory_chain),
    ]:
        try:
            fn()
            note(name + ' DONE')
        except Exception as e:
            note(name + ' EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
        print('::error::batch254 part: ' + name)
        sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch254 ' + str(line)[:800])
    print('::error::batch254 END lines=' + str(len(report)))


main()