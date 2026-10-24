#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch285: 「每个对话单独设模型」总开关（UI 可控）

【现状（实读 snapshot 确认，非推断）】
batch234(A4) 之后，聊天页换模型一律写 conversation.config.chatModelId（会话级）：
  ChatVM.setChatModel -> chatService.setConversationModel(_conversationId, model.id)
读取侧：ChatService 用 settings.getAssistantOf(conversation) / settings.getChatModelOf(conversation)
        ChatVM.currentChatModel 用 getChatModelOf（batch254）
        ChatInput 的 ModelSelector / 能力判断用 conversationChatModelId ?: assistant.chatModelId ?: settings.chatModelId
       （batch255/268，ChatPage 传 conversation.config?.chatModelId）
=> 目前没有"回退到跟随助手"的开关。

【本批新增】
DisplaySetting.perConversationModel: Boolean = true
  开(默认) = 保持现状：每个对话单独设模型，互不影响
  关       = 所有对话跟随助手模型（会话固定值被忽略，不删数据）

改动五处：
 1. PreferencesStore.kt   DisplaySetting 末尾加字段（默认 true，旧 JSON 无该字段直接取默认）
 2. ConversationConfig.kt 三处闸门：
      getChatModelOf  → 关：直接返回助手模型（不看 config）
      getAssistantOf  → 关：会话视角的 chatModelId 用助手自身（其余会话字段不变）
      bindConfig      → 关：新会话不把模型固定进 config（chatModelId = null）
 3. ChatVM.kt    setChatModel → 关：写会话所属助手(conversation.assistantId)的 chatModelId
                               开：沿用 batch234 的 setConversationModel
 4. ChatPage.kt  conversationChatModelId 传参 → 关：传 null，输入栏回退助手模型（显示与实际一致）
 5. SettingPreferencesUIPage.kt  消息显示卡片加开关行（冲在 rhPlanBar228 之前）

【为什么不改 ChatService】
batch232(A3) 已把 ChatService 的全部模型/助手解析收敛到 getAssistantOf / getChatModelOf，
本批改这两个函数即可覆盖发送、重跑、标题等全部链路。

五查:
 1. import 清单: 五个文件零新增 import（Settings/DisplaySetting/Uuid 均已在作用域）
 2. 同文件冲突: 锚点全部取 snapshot(CI 真形态)唯一行；批号 285 排在全部在链脚本之后
 3. 作用域: ChatVM 的 settings/conversation 是 StateFlow；ChatPage 的 setting: Settings；
    ConversationConfig 内 displaySetting 是 Settings 属性；UI 页 displaySetting 是局部状态
 4. 括号配对: 每处插入自配平，整文件 balance 前后差必须为 0（断言）
 5. 函数签名: 零改动（setChatModel 签名不变，assistant 参数保持向后兼容）

Python 三查:
 1 引号: 无裸引号拼接，文案用中文引号；Q 未使用
 2 换行: NL 显式 concat，禁用 join/f-string/walrus
 3 helper: read/write/balance/ind_of/lines_to_text 全部先定义后用；异常记录后继续
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
BATCH = 'batch285'
MARK = 'rhPerConvModel285'
DIAG = 'ci_diag_batch285.txt'

PREF = 'app/src/main/java/me/rerere/rikkahub/data/datastore/PreferencesStore.kt'
CONF = 'app/src/main/java/me/rerere/rikkahub/data/model/ConversationConfig.kt'
VM = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatVM.kt'
PAGE = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'
UI = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPreferencesUIPage.kt'

report = []


def note(msg):
    report.append(str(msg)[:900])


def balance(text):
    return (text.count('(') - text.count(')')
            + text.count('{') - text.count('}')
            + text.count('[') - text.count(']'))


def read(path):
    p = ROOT / path
    if not p.exists():
        return None
    try:
        return p.read_text(encoding='utf-8')
    except Exception:
        return None


def write(path, text):
    p = ROOT / path
    if not p.parent.exists():
        p.parent.mkdir(parents=True)
    p.write_text(text, encoding='utf-8')


def ind_of(line):
    s = line.lstrip()
    return line[:len(line) - len(s)]


def lines_to_text(lines):
    out = ''
    for idx, line in enumerate(lines):
        if idx > 0:
            out += NL
        out += line
    return out


def hits_of(lines, needle):
    return [i for i, ln in enumerate(lines) if ln.strip() == needle]


def patch_pref():
    t = read(PREF)
    if t is None:
        note('ABORT pref missing')
        return
    if MARK in t:
        note('pref already')
        return
    needle = 'val liteStreamRender: Boolean = false,'
    lines = t.split(NL)
    hits = hits_of(lines, needle)
    if len(hits) != 1:
        note('ABORT pref anchor count=' + str(len(hits)))
        return
    i = hits[0]
    ind = ind_of(lines[i])
    add = [
        ind + '// ' + MARK + ': 关闭后所有对话跟随助手模型，忽略会话上固定的模型；默认开启保持既有会话级行为',
        ind + 'val perConversationModel: Boolean = true,',
    ]
    lines2 = lines[:i + 1] + add + lines[i + 1:]
    t2 = lines_to_text(lines2)
    if balance(t2) != balance(t):
        note('ABORT pref balance')
        return
    if 'val perConversationModel: Boolean = true,' not in t2:
        note('ABORT pref selfcheck')
        return
    write(PREF, t2)
    note('pref OK: DisplaySetting.perConversationModel=true')


def patch_conf():
    t = read(CONF)
    if t is None:
        note('ABORT conf missing (batch229 not applied?)')
        return
    if MARK in t:
        note('conf already')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    # 1) getChatModelOf 闸门
    a = hits_of(lines, 'val config = conversation.config ?: return assistantModel')
    if len(a) == 1:
        i = a[0]
        ind = ind_of(lines[i])
        lines = lines[:i] + [
            ind + '// ' + MARK + ': 关闭总开关时忽略会话固定模型，始终跟随助手',
            ind + 'if (!displaySetting.perConversationModel) return assistantModel',
        ] + lines[i:]
    else:
        note('ABORT conf model anchor count=' + str(len(a)))

    # 2) getAssistantOf 闸门
    b = hits_of(lines, 'val assistant = getStoredAssistantOf(conversation).withConversation(conversation)')
    if len(b) == 1:
        i = b[0]
        ind = ind_of(lines[i])
        repl = [
            ind + 'val rhStoredAssistant = getStoredAssistantOf(conversation)',
            ind + '// ' + MARK + ': 关闭总开关时会话视角的模型也回到助手自身，其余会话字段不变',
            ind + 'val assistant = if (displaySetting.perConversationModel) {',
            ind + '    rhStoredAssistant.withConversation(conversation)',
            ind + '} else {',
            ind + '    rhStoredAssistant.withConversation(conversation).copy(chatModelId = rhStoredAssistant.chatModelId)',
            ind + '}',
        ]
        lines = lines[:i] + repl + lines[i + 1:]
    else:
        note('ABORT conf assistant anchor count=' + str(len(b)))

    # 3) bindConfig 闸门
    c = hits_of(lines, 'config = assistant.toConversationConfig().copy(chatModelId = model?.id, builtInSearch = builtInSearch),')
    if len(c) == 1:
        i = c[0]
        ind = ind_of(lines[i])
        lines[i] = (ind
                    + 'config = assistant.toConversationConfig().copy(chatModelId = if (settings.displaySetting.perConversationModel) model?.id else null, builtInSearch = builtInSearch), // '
                    + MARK)
    else:
        note('ABORT conf bind anchor count=' + str(len(c)))

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('ABORT conf balance ' + str(bal0) + ' -> ' + str(balance(t2)))
        return
    for need in [
        'if (!displaySetting.perConversationModel) return assistantModel',
        'val rhStoredAssistant = getStoredAssistantOf(conversation)',
        'if (settings.displaySetting.perConversationModel) model?.id else null',
    ]:
        if need not in t2:
            note('ABORT conf selfcheck missing: ' + need)
            return
    write(CONF, t2)
    note('conf OK: model/assistant/bind gated by switch')


def patch_vm():
    t = read(VM)
    if t is None:
        note('ABORT vm missing')
        return
    if MARK in t:
        note('vm already')
        return
    bal0 = balance(t)
    lines = t.split(NL)
    sig = 'fun setChatModel(assistant: Assistant, model: Model) {'
    hits = hits_of(lines, sig)
    if len(hits) != 1:
        note('ABORT vm signature count=' + str(len(hits)))
        return
    i = hits[0]
    depth = 0
    end = -1
    for j in range(i, len(lines)):
        depth += lines[j].count('{') - lines[j].count('}')
        if j > i and depth == 0:
            end = j
            break
    if end < 0:
        note('ABORT vm fn end not found')
        return
    # 正反推演: 原函数体只有 viewModelScope.launch { chatService.setConversationModel(...) }
    # 因此 end 必须落在 launch 的闭合花括号之后，且区间内必须含 setConversationModel
    seg = NL.join(lines[i:end + 1])
    if 'chatService.setConversationModel(_conversationId, model.id)' not in seg:
        note('ABORT vm fn body unexpected (no setConversationModel)')
        return
    ind = ind_of(lines[i])
    p1 = ind + '    '
    p2 = ind + '        '
    repl = [
        ind + 'fun setChatModel(assistant: Assistant, model: Model) {',
        p1 + 'viewModelScope.launch {',
        p2 + '// ' + MARK + ': 总开关关闭 -> 写会话所属助手，回到"所有对话跟随助手模型"的旧行为',
        p2 + 'if (!settings.value.displaySetting.perConversationModel) {',
        p2 + '    val rhTargetAssistantId = conversation.value.assistantId',
        p2 + '    settingsStore.update { settings ->',
        p2 + '        settings.copy(',
        p2 + '            assistants = settings.assistants.map {',
        p2 + '                if (it.id == rhTargetAssistantId) {',
        p2 + '                    it.copy(chatModelId = model.id)',
        p2 + '                } else {',
        p2 + '                    it',
        p2 + '                }',
        p2 + '            }',
        p2 + '        )',
        p2 + '    }',
        p2 + '    return@launch',
        p2 + '}',
        p2 + '// [batch234] A4: 写当前会话自己的 config.chatModelId, 不动助手(会话级)',
        p2 + 'chatService.setConversationModel(_conversationId, model.id)',
        p1 + '}',
        ind + '}',
    ]
    lines2 = lines[:i] + repl + lines[end + 1:]
    t2 = lines_to_text(lines2)
    if balance(t2) != bal0:
        note('ABORT vm balance ' + str(bal0) + ' -> ' + str(balance(t2)))
        return
    for need in [
        'if (!settings.value.displaySetting.perConversationModel) {',
        'val rhTargetAssistantId = conversation.value.assistantId',
        'return@launch',
        'chatService.setConversationModel(_conversationId, model.id)',
    ]:
        if need not in t2:
            note('ABORT vm selfcheck missing: ' + need)
            return
    write(VM, t2)
    note('vm OK: off -> assistant model, on -> conversation model')


def patch_page():
    t = read(PAGE)
    if t is None:
        note('ABORT page missing')
        return
    if MARK in t:
        note('page already')
        return
    bal0 = balance(t)
    lines = t.split(NL)
    hits = hits_of(lines, 'conversationChatModelId = conversation.config?.chatModelId,')
    if len(hits) != 1:
        note('ABORT page anchor count=' + str(len(hits)))
        return
    i = hits[0]
    ind = ind_of(lines[i])
    lines[i] = (ind
                + 'conversationChatModelId = if (setting.displaySetting.perConversationModel) conversation.config?.chatModelId else null, // '
                + MARK)
    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('ABORT page balance')
        return
    if 'if (setting.displaySetting.perConversationModel) conversation.config?.chatModelId else null' not in t2:
        note('ABORT page selfcheck')
        return
    write(PAGE, t2)
    note('page OK: switch off -> null (input bar falls back to assistant model)')


def patch_ui():
    t = read(UI)
    if t is None:
        note('ABORT ui missing')
        return
    if MARK in t:
        note('ui already')
        return
    bal0 = balance(t)
    lines = t.split(NL)
    hits = hits_of(lines, '// rhPlanBar228: 计划细条显示开关')
    if len(hits) != 1:
        note('ABORT ui anchor count=' + str(len(hits)))
        return
    i = hits[0]
    ind = ind_of(lines[i])
    block = [
        ind + '// ' + MARK + ': 每个对话单独设模型的总开关',
        ind + 'item(',
        ind + '    headlineContent = { Text("每个对话单独设模型") },',
        ind + '    supportingContent = { Text("开启后，聊天页切换模型只影响当前对话；关闭后所有对话跟随助手模型") },',
        ind + '    trailingContent = {',
        ind + '        Switch(',
        ind + '            checked = displaySetting.perConversationModel,',
        ind + '            onCheckedChange = {',
        ind + '                updateDisplaySetting(displaySetting.copy(perConversationModel = it))',
        ind + '            }',
        ind + '        )',
        ind + '    },',
        ind + ')',
    ]
    lines2 = lines[:i] + block + lines[i:]
    t2 = lines_to_text(lines2)
    if balance(t2) != bal0:
        note('ABORT ui balance')
        return
    for need in [
        'checked = displaySetting.perConversationModel,',
        'updateDisplaySetting(displaySetting.copy(perConversationModel = it))',
    ]:
        if need not in t2:
            note('ABORT ui selfcheck missing: ' + need)
            return
    write(UI, t2)
    note('ui OK: switch row added to message display card')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::' + BATCH + ' diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::' + BATCH + ' diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    steps = [
        ('1 DisplaySetting field', patch_pref),
        ('2 ConversationConfig gates', patch_conf),
        ('3 ChatVM setChatModel', patch_vm),
        ('4 ChatPage pass conversation id', patch_page),
        ('5 Settings UI switch', patch_ui),
    ]
    for name, fn in steps:
        try:
            fn()
        except Exception as e:
            note(name + ' EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
        print('::error::' + BATCH + ' part: ' + name)
        sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::' + BATCH + ' ' + str(line)[:800])
    print('::error::' + BATCH + ' END lines=' + str(len(report)))


main()