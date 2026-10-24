#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch287: 完全回退 A4/会话级模型 —— 硬回退到旧版行为（用户要求：模型切换要可靠、可完全回退）

用户反馈: A4(会话级模型)设计总有问题, 切不了模型/功能不正常, 要求能完全回退。

硬回退做法(行为无条件回旧, 不依赖开关/持久化值 —— 这是最可靠的"完全回退"):
  1. ConversationConfig.kt
     - getChatModelOf: 删除 config 咨询, 直接 return 助手模型
     - getAssistantOf: 会话视角的 assistant 直接用 stored 助手(不再叠加 config)
     - bindConfig: 直接 return this(不再拍快照)
  2. ChatVM.setChatModel: 写回助手(assistants.map), 不再调 setConversationModel
  3. ChatPage: conversationChatModelId 传 null(输入栏回退助手模型)

A 的代码与数据保留(ConversationConfig 数据类 / DB config 列 / accessors / 设置页开关都还在),
只是行为不再消费它 —— 想恢复 A 时把这三处 accessor 与两处调用改回来即可。

幂等 marker rhA4Rollback287; 各锚点唯一; warn-only; 括号差值断言; 失败写 ci_diag。
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
BATCH = 'batch287'
MARK = 'rhA4Rollback287'
DIAG = 'ci_diag_batch287.txt'

CONF = 'app/src/main/java/me/rerere/rikkahub/data/model/ConversationConfig.kt'
VM = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatVM.kt'
PAGE = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'

report = []


def note(m):
    report.append(str(m)[:900])


def read(p):
    q = ROOT / p
    if not q.exists():
        return None
    try:
        return q.read_text(encoding='utf-8')
    except Exception:
        return None


def write(p, t):
    q = ROOT / p
    if not q.parent.exists():
        q.parent.mkdir(parents=True)
    q.write_text(t, encoding='utf-8')


def bal(t):
    return (t.count('(') - t.count(')')
            + t.count('{') - t.count('}')
            + t.count('[') - t.count(']'))


def sub_once(path, old, new, tag):
    t = read(path)
    if t is None:
        note(tag + ' missing')
        return False
    if MARK in t:
        note(tag + ' already')
        return True
    n = t.count(old)
    if n != 1:
        note(tag + ' anchor count=' + str(n))
        return False
    b0 = bal(t)
    out = t.replace(old, new, 1)
    if bal(out) != b0:
        note(tag + ' balance ' + str(b0) + '->' + str(bal(out)))
        return False
    write(path, out)
    note(tag + ' OK')
    return True


def patch_conf():
    p = CONF
    t = read(p)
    if t is None:
        note('conf missing')
        return
    if MARK in t:
        note('conf already')
        return

    old_model = '''    // rhPerConvModel285: 关闭总开关时忽略会话固定模型，始终跟随助手
    if (!displaySetting.perConversationModel) return assistantModel
    val config = conversation.config ?: return assistantModel
    // 固定的模型被删除后退回助手当前的模型，内置搜索也跟随该模型自身的开关
    val model = findModelById(config.chatModelId) ?: return assistantModel
    return model.copy(
        tools = if (config.builtInSearch) model.tools + BuiltInTools.Search else model.tools - BuiltInTools.Search
    )'''
    new_model = '''    // [batch287] 完全回退：不使用会话固定配置，始终跟随助手模型
    return assistantModel'''
    if t.count(old_model) != 1:
        note('conf model anchor count=' + str(t.count(old_model)))
    else:
        t = t.replace(old_model, new_model, 1)
        note('conf model OK')

    old_asst = '''    val assistant = if (displaySetting.perConversationModel) {
        rhStoredAssistant.withConversation(conversation)
    } else {
        rhStoredAssistant.withConversation(conversation).copy(chatModelId = rhStoredAssistant.chatModelId)
    }'''
    new_asst = '''    val assistant = rhStoredAssistant // [batch287] 完全回退：直接用 stored 助手'''
    if t.count(old_asst) != 1:
        note('conf assistant anchor count=' + str(t.count(old_asst)))
    else:
        t = t.replace(old_asst, new_asst, 1)
        note('conf assistant OK')

    old_bind = '''    val model = settings.getChatModelOf(this)
    val builtInSearch = model != null && BuiltInTools.Search in model.tools
    val config = config
    if (config != null) {
        if (model == null || model.id == config.chatModelId) return this
        return copy(config = config.copy(chatModelId = model.id, builtInSearch = builtInSearch))
    }
    val assistant = settings.getAssistantOf(this)
    return copy(
        config = assistant.toConversationConfig().copy(chatModelId = if (settings.displaySetting.perConversationModel) model?.id else null, builtInSearch = builtInSearch), // rhPerConvModel285
        // 旧版本允许会话单独绑定注入，这类会话保留自己的绑定
        modeInjectionIds = modeInjectionIds.ifEmpty { assistant.modeInjectionIds },
        lorebookIds = lorebookIds.ifEmpty { assistant.lorebookIds },
    )'''
    new_bind = '''    // [batch287] 完全回退：不在会话上固定配置快照
    return this'''
    if t.count(old_bind) != 1:
        note('conf bind anchor count=' + str(t.count(old_bind)))
    else:
        t = t.replace(old_bind, new_bind, 1)
        note('conf bind OK')

    if 'batch287' in t:
        write(p, t + NL + '// ' + MARK)
    else:
        note('conf no edits applied')


def patch_vm():
    old_fn = '''    fun setChatModel(assistant: Assistant, model: Model) {
        viewModelScope.launch {
            // rhPerConvModel285: 总开关关闭 -> 写会话所属助手，回到"所有对话跟随助手模型"的旧行为
            if (!settings.value.displaySetting.perConversationModel) {
                val rhTargetAssistantId = conversation.value.assistantId
                settingsStore.update { settings ->
                    settings.copy(
                        assistants = settings.assistants.map {
                            if (it.id == rhTargetAssistantId) {
                                it.copy(chatModelId = model.id)
                            } else {
                                it
                            }
                        }
                    )
                }
                return@launch
            }
            // [batch234] A4: 写当前会话自己的 config.chatModelId, 不动助手(会话级)
            chatService.setConversationModel(_conversationId, model.id)
        }
    }'''
    new_fn = '''    fun setChatModel(assistant: Assistant, model: Model) {
        viewModelScope.launch {
            // [batch287] 完全回退：切换模型写回助手(旧版行为)，所有对话跟随助手
            settingsStore.update { settings ->
                settings.copy(
                    assistants = settings.assistants.map {
                        if (it.id == assistant.id) {
                            it.copy(chatModelId = model.id)
                        } else {
                            it
                        }
                    })
            }
        }
    }'''
    sub_once(VM, old_fn, new_fn, 'vm')


def patch_page():
    old_line = 'conversationChatModelId = if (setting.displaySetting.perConversationModel) conversation.config?.chatModelId else null, // rhPerConvModel285'
    new_line = 'conversationChatModelId = null, // [batch287] 完全回退：输入栏跟随助手模型'
    sub_once(PAGE, old_line, new_line, 'page')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::' + BATCH + ' diag chars=' + str(len(body)))
    except Exception as e:
        print('::error::' + BATCH + ' diag write FAILED ' + str(e)[:150])


def main():
    try:
        patch_conf()
    except Exception as e:
        note('conf EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
    print('::error::' + BATCH + ' part: conf')
    try:
        patch_vm()
    except Exception as e:
        note('vm EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
    print('::error::' + BATCH + ' part: vm')
    try:
        patch_page()
    except Exception as e:
        note('page EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
    print('::error::' + BATCH + ' part: page')
    write_diag()
    for line in report:
        print('::error::' + BATCH + ' ' + str(line)[:700])
    print('::error::' + BATCH + ' END lines=' + str(len(report)))


main()