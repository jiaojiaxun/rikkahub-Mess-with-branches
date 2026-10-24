#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch299: 模型切换「旧版/新版」单一总开关（用户最终口径）

用户澄清：
  旧版 = 在某个对话里切换模型，会写到助手级，该助手的其他对话一起变（默认要这个）
  新版 = 固定当前对话自己的模型，其他对话不变
  只要一个开关统一控制，不要多套模型 UI。

本补丁是最终裁决层，排在当前所有 patch 之后：
  - 覆盖 batch285/286/287 与后续 batch287_a4_rollback 的互相覆盖结果
  - 关闭（默认）= 完整旧版：getChatModelOf 直接助手模型；getAssistantOf 直接 stored；
    bindConfig 不写快照；ChatVM 写助手模型
  - 开启 = 新版：getChatModelOf/getAssistantOf 消费会话 config；bindConfig 拍快照；
    ChatVM 写 conversation.config.chatModelId
  - ChatPage 的输入栏模型 id 改用 getChatModelOf(conversation)?.id，
    保证「显示、能力判断、实际发送、切换写入」同源
  - 设置页只保留原来那一行开关，文案改成旧版/新版，不新增任何模型 UI

五查:
 1. import: 五文件零新增。ChatPage 已有 getChatModelOf / getCurrentAssistant import；
    ChatVM 已有 StateFlow/settings/conversation；ConversationConfig 已有 Settings/Model/BuiltInTools。
 2. 同文件冲突: 本批是最大批号 299，在 285/286/287/287_rollback/289 之后执行；
    只替换当前真形态的 5 个落点，且五处全部成功才统一写盘，失败零写入。
 3. 作用域: settings/conversation 是 ChatVM 的 StateFlow；setting/conversation 在 ChatPage 的
    ChatPageContent 作用域；displaySetting 是 Settings 属性；Swift? 无。
 4. 括号配对: 每个替换前后文件 balance 必须不变；ChatVM 新块花括号自配平。
 5. 函数签名: 全部不变（setChatModel 参数保持，ChatInput 参数保持）。

Python 三查:
 1. 引号统一用三引号固定块；INSERT 用单行折行常量，无裸引号跨行拼接。
 2. 不用 f-string / walrus / join；NL 显式赋值，行拼接走 lines_to_text。
 3. helper 全部先定义后用；每文件独立 transform，任何一步失败 => 不写任何文件 + diag。

验证: 本脚本写 ci_diag_batch299_model_switch_mode.txt，并在 ::error 输出每一步。
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
BATCH = 'batch299'
MARK = 'rhPerConversationModel299'
DIAG = 'ci_diag_batch299_model_switch_mode.txt'

PREF = 'app/src/main/java/me/rerere/rikkahub/data/datastore/PreferencesStore.kt'
CONF = 'app/src/main/java/me/rerere/rikkahub/data/model/ConversationConfig.kt'
VM = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatVM.kt'
PAGE = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'
UI = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPreferencesUIPage.kt'

report = []


def note(msg):
    report.append(str(msg)[:1000])


def read(path):
    p = ROOT / path
    if not p.exists():
        note('MISSING ' + path)
        return None
    try:
        return p.read_text(encoding='utf-8')
    except Exception as exc:
        note('READ-FAIL ' + path + ' ' + type(exc).__name__ + ' ' + str(exc)[:200])
        return None


def lines_to_text(lines):
    out = ''
    for idx, line in enumerate(lines):
        if idx > 0:
            out += NL
        out += line
    return out


def ind_of(line):
    body = line.lstrip()
    return line[:len(line) - len(body)]


def balance(text):
    return (text.count('(') - text.count(')')
            + text.count('{') - text.count('}')
            + text.count('[') - text.count(']'))


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        note(label + ' anchor-count=' + str(count) + ' need=1')
        return None
    before = balance(text)
    out = text.replace(old, new, 1)
    if balance(out) != before:
        note(label + ' balance ' + str(before) + ' -> ' + str(balance(out)))
        return None
    note(label + ' OK')
    return out


def replace_line(text, predicate, make_line, label):
    lines = text.split(NL)
    hits = []
    for i, line in enumerate(lines):
        if predicate(line.strip()):
            hits.append(i)
    if len(hits) != 1:
        note(label + ' line-count=' + str(len(hits)) + ' need=1')
        return None
    idx = hits[0]
    before = balance(text)
    lines[idx] = make_line(ind_of(lines[idx]))
    out = lines_to_text(lines)
    if balance(out) != before:
        note(label + ' balance changed')
        return None
    note(label + ' OK')
    return out


def transform_pref():
    text = read(PREF)
    if text is None:
        return None
    if MARK in text:
        note('pref already')
        return text

    def make(ind):
        return ind + 'val perConversationModel: Boolean = false, // ' + MARK + ': false=旧版助手级(默认)；true=新版按对话固定'

    out = replace_line(
        text,
        lambda s: s.startswith('val perConversationModel: Boolean ='),
        make,
        'pref-field',
    )
    if out is not None:
        return out

    # 防御性兜底：字段完全不存在时插在 DisplaySetting 最后字段之后
    anchor = '    val liteStreamRender: Boolean = false,'
    if text.count(anchor) == 1:
        block = NL + NL + '    val perConversationModel: Boolean = false, // ' + MARK + ': 默认旧版'
        out2 = replace_once(text, anchor, anchor + block, 'pref-insert')
        if out2 is not None:
            return out2
    note('pref ABORT: neither field nor reliable insert anchor')
    return None


def transform_conf():
    text = read(CONF)
    if text is None:
        return None
    if MARK in text:
        note('conf already')
        return text

    old_model = NL.join([
        '    // [batch287] 完全回退：不使用会话固定配置，始终跟随助手模型',
        '    return assistantModel',
    ])
    new_model = NL.join([
        '    // ' + MARK + ': 旧版直接助手模型；新版才消费会话固定模型',
        '    if (!displaySetting.perConversationModel) return assistantModel',
        '    val config = conversation.config ?: return assistantModel',
        '    val model = findModelById(config.chatModelId) ?: return assistantModel',
        '    return model.copy(',
        '        tools = if (config.builtInSearch) model.tools + BuiltInTools.Search else model.tools - BuiltInTools.Search',
        '    )',
    ])
    out = replace_once(text, old_model, new_model, 'conf-model')
    if out is None:
        return None

    old_assistant = NL.join([
        '    // rhPerConvModel285: 关闭总开关时会话视角的模型也回到助手自身，其余会话字段不变',
        '    val assistant = rhStoredAssistant // [batch287] 完全回退：直接用 stored 助手',
    ])
    new_assistant = NL.join([
        '    // ' + MARK + ': 关闭=完整旧版(不覆盖任何会话配置)；开启=会话视角覆盖',
        '    val assistant = if (displaySetting.perConversationModel) {',
        '        rhStoredAssistant.withConversation(conversation)',
        '    } else {',
        '        rhStoredAssistant',
        '    }',
    ])
    out = replace_once(out, old_assistant, new_assistant, 'conf-assistant')
    if out is None:
        return None

    old_bind = NL.join([
        'fun Conversation.bindConfig(settings: Settings): Conversation {',
        '    // [batch287] 完全回退：不在会话上固定配置快照',
        '    return this',
        '}',
    ])
    new_bind = NL.join([
        'fun Conversation.bindConfig(settings: Settings): Conversation {',
        '    // ' + MARK + ': 旧版不写会话快照；新版才固定当前会话配置',
        '    if (!settings.displaySetting.perConversationModel) return this',
        '    val model = settings.getChatModelOf(this)',
        '    val builtInSearch = model != null && BuiltInTools.Search in model.tools',
        '    val config = config',
        '    if (config != null) {',
        '        if (model == null || model.id == config.chatModelId) return this',
        '        return copy(config = config.copy(chatModelId = model.id, builtInSearch = builtInSearch))',
        '    }',
        '    val assistant = settings.getAssistantOf(this)',
        '    return copy(',
        '        config = assistant.toConversationConfig().copy(chatModelId = model?.id, builtInSearch = builtInSearch),',
        '        modeInjectionIds = modeInjectionIds.ifEmpty { assistant.modeInjectionIds },',
        '        lorebookIds = lorebookIds.ifEmpty { assistant.lorebookIds },',
        '    )',
        '}',
    ])
    out = replace_once(out, old_bind, new_bind, 'conf-bind')
    if out is None:
        return None

    checks = [
        'if (!displaySetting.perConversationModel) return assistantModel',
        'if (displaySetting.perConversationModel) {',
        'if (!settings.displaySetting.perConversationModel) return this',
    ]
    for need in checks:
        if need not in out:
            note('conf selfcheck missing ' + need)
            return None
    return out


def transform_vm():
    text = read(VM)
    if text is None:
        return None
    if MARK in text:
        note('vm already')
        return text

    old_fn = NL.join([
        '    fun setChatModel(assistant: Assistant, model: Model) {',
        '        viewModelScope.launch {',
        '            // [batch287] 完全回退：切换模型写回助手(旧版行为)，所有对话跟随助手',
        '            settingsStore.update { settings ->',
        '                settings.copy(',
        '                    assistants = settings.assistants.map {',
        '                        if (it.id == assistant.id) {',
        '                            it.copy(chatModelId = model.id)',
        '                        } else {',
        '                            it',
        '                        }',
        '                    })',
        '            }',
        '        }',
        '    }',
    ])
    new_fn = NL.join([
        '    fun setChatModel(assistant: Assistant, model: Model) {',
        '        viewModelScope.launch {',
        '            if (settings.value.displaySetting.perConversationModel) {',
        '                // ' + MARK + ': 新版——只固定当前对话',
        '                chatService.setConversationModel(_conversationId, model.id)',
        '                return@launch',
        '            }',
        '            // ' + MARK + ': 旧版——写助手级，该助手的其他对话一起变',
        '            val rhTargetAssistantId = settings.value.assistants',
        '                .firstOrNull { it.id == conversation.value.assistantId }?.id',
        '                ?: assistant.id',
        '            settingsStore.update { settings ->',
        '                settings.copy(',
        '                    assistants = settings.assistants.map {',
        '                        if (it.id == rhTargetAssistantId) {',
        '                            it.copy(chatModelId = model.id)',
        '                        } else {',
        '                            it',
        '                        }',
        '                    })',
        '            }',
        '        }',
        '    }',
    ])
    out = replace_once(text, old_fn, new_fn, 'vm-setChatModel')
    if out is None:
        return None
    for need in [
        'if (settings.value.displaySetting.perConversationModel) {',
        'chatService.setConversationModel(_conversationId, model.id)',
        'val rhTargetAssistantId = settings.value.assistants',
    ]:
        if need not in out:
            note('vm selfcheck missing ' + need)
            return None
    return out


def transform_page():
    text = read(PAGE)
    if text is None:
        return None
    if MARK in text:
        note('page already')
        return text
    if 'import me.rerere.rikkahub.data.model.getChatModelOf' not in text:
        note('page missing getChatModelOf import')
        return None

    def make(ind):
        return ind + 'conversationChatModelId = setting.getChatModelOf(conversation)?.id, // ' + MARK

    out = replace_line(
        text,
        lambda s: s.startswith('conversationChatModelId ='),
        make,
        'page-chat-input-model-id',
    )
    if out is None:
        return None
    if out.count(MARK) != 1:
        note('page marker count=' + str(out.count(MARK)))
        return None
    return out


def transform_ui():
    text = read(UI)
    if text is None:
        return None
    if MARK in text:
        note('ui already')
        return text

    out = replace_line(
        text,
        lambda s: s == '// rhPerConvModel285: 每个对话单独设模型的总开关',
        lambda ind: ind + '// ' + MARK + ': 唯一开关，统一控制旧版/新版模型切换',
        'ui-comment',
    )
    if out is None:
        return None

    out = replace_line(
        out,
        lambda s: s == 'headlineContent = { Text("每个对话单独设模型") },',
        lambda ind: ind + 'headlineContent = { Text("按对话固定模型（新版）") },',
        'ui-headline',
    )
    if out is None:
        return None

    out = replace_line(
        out,
        lambda s: s == 'supportingContent = { Text("开启后，聊天页切换模型只影响当前对话；关闭后所有对话跟随助手模型") },',
        lambda ind: ind + 'supportingContent = { Text("关闭(默认)=旧版：切换模型会同步到该助手的其他对话；开启=新版：只影响当前对话") },',
        'ui-supporting',
    )
    if out is None:
        return None
    if '关闭(默认)=旧版' not in out:
        note('ui selfcheck missing')
        return None
    return out


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::' + BATCH + ' diag written chars=' + str(len(body)))
    except Exception as exc:
        print('::error::' + BATCH + ' diag write FAILED ' + str(exc)[:200])
    sys.stdout.flush()


def main():
    jobs = [
        ('pref', PREF, transform_pref),
        ('conf', CONF, transform_conf),
        ('vm', VM, transform_vm),
        ('page', PAGE, transform_page),
        ('ui', UI, transform_ui),
    ]
    results = {}
    all_ok = True
    for name, path, fn in jobs:
        try:
            result = fn()
        except Exception as exc:
            note(name + ' EXCEPTION ' + type(exc).__name__ + ' ' + str(exc)[:300])
            result = None
        if result is None:
            all_ok = False
            note(name + ' FAILED')
        else:
            results[path] = result
            note(name + ' READY')
        print('::error::' + BATCH + ' part: ' + name)
        sys.stdout.flush()

    if all_ok:
        try:
            for path, content in results.items():
                target = ROOT / path
                if not target.parent.exists():
                    target.parent.mkdir(parents=True)
                target.write_text(content, encoding='utf-8')
                note('WROTE ' + path)
        except Exception as exc:
            all_ok = False
            note('WRITE EXCEPTION ' + type(exc).__name__ + ' ' + str(exc)[:300])
    else:
        note('NO FILE WRITTEN (all-or-nothing)')

    if all_ok:
        note('RESULT OK: four files? count=' + str(len(results)))
    else:
        note('RESULT ABORT: no partial writes')

    write_diag()
    for line in report:
        print('::error::' + BATCH + ' ' + str(line)[:900])
    print('::error::' + BATCH + ' END lines=' + str(len(report)))


main()