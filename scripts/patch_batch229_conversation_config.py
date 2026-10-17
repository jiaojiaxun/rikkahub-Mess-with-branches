#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch229: A1 地基 —— ConversationConfig.kt(新文件) + Conversation 加 config 字段

A 移植(ConversationConfig 会话级固定配置)的第一批。本批只做地基，不动 DB/ChatService:
  1. 新建 data/model/ConversationConfig.kt —— 上游 rikkahub/rikkahub master 全文
     (sha a7a3fd54)，内容逐项核实过 fork 兼容:
       依赖 Assistant.chatModelId/reasoningLevel/enableWebSearch/mcpServers/workspaceId/
       enabledSkills/modeInjectionIds/lorebookIds —— fork 全有 ✓
       依赖 Conversation.modeInjectionIds/lorebookIds/workspaceCwd —— fork 全有 ✓
       依赖 Settings.mcpServers/modeInjections/lorebooks + findModelById/getAssistantById/
       getCurrentAssistant —— fork 全有 ✓
  2. Conversation.kt 加 `val config: ConversationConfig? = null` 字段
     (锚点 `val workspaceCwd: String? = null,` 唯一)。

不动 DB(不持久化=仅内存态, 后续 A2 加 config 列 + 34→35 迁移才落库)。
分歧点(已记录待办): fork 的 Conversation.chatModelId(既有)与 config.chatModelId 重叠,
  A 收编时处理, 本批不碰。

幂等 marker rhConversationConfig; 锚点唯一; warn-only; 括号差值断言。
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
BATCH = 'batch229'
MARK = 'rhConversationConfig'
CONV = 'app/src/main/java/me/rerere/rikkahub/data/model/Conversation.kt'
NEWFILE = 'app/src/main/java/me/rerere/rikkahub/data/model/ConversationConfig.kt'

CONFIG_KT = r'''package me.rerere.rikkahub.data.model

import kotlinx.serialization.Serializable
import me.rerere.ai.core.ReasoningLevel
import me.rerere.ai.provider.BuiltInTools
import me.rerere.ai.provider.Model
import me.rerere.rikkahub.data.datastore.Settings
import me.rerere.rikkahub.data.datastore.findModelById
import me.rerere.rikkahub.data.datastore.getAssistantById
import me.rerere.rikkahub.data.datastore.getCurrentAssistant
import kotlin.uuid.Uuid

/**
 * 会话开始后固定在会话上的配置。
 *
 * 新会话没有这份配置，聊天页里的切换直接改助手；会话落库时从助手拍一份快照，
 * 之后的切换只影响当前会话，别处的改动不会打乱它的上下文和缓存。
 * 模式注入和 Lorebook 同样随会话固定，沿用 [Conversation.modeInjectionIds] 与 [Conversation.lorebookIds]。
 */
@Serializable
data class ConversationConfig(
    val chatModelId: Uuid? = null,
    val reasoningLevel: ReasoningLevel = ReasoningLevel.AUTO,
    val enableWebSearch: Boolean = false,
    val builtInSearch: Boolean = false, // 模型内置搜索，覆盖模型自身的开关
    val mcpServers: Set<Uuid> = emptySet(),
    val workspaceId: Uuid? = null,
    val enabledSkills: Set<String> = emptySet(),
)

// 内置搜索是模型的开关，不在助手上，由调用方另行填入
private fun Assistant.toConversationConfig() = ConversationConfig(
    chatModelId = chatModelId,
    reasoningLevel = reasoningLevel,
    enableWebSearch = enableWebSearch,
    mcpServers = mcpServers,
    workspaceId = workspaceId,
    enabledSkills = enabledSkills,
)

private fun Assistant.withConversationConfig(config: ConversationConfig) = copy(
    chatModelId = config.chatModelId,
    reasoningLevel = config.reasoningLevel,
    enableWebSearch = config.enableWebSearch,
    mcpServers = config.mcpServers,
    workspaceId = config.workspaceId,
    enabledSkills = config.enabledSkills,
)

/** 会话视角下的助手：会话开始后，会话持有的字段覆盖助手自身的值。 */
fun Assistant.withConversation(conversation: Conversation): Assistant {
    val config = conversation.config ?: return this
    return withConversationConfig(config).copy(
        modeInjectionIds = conversation.modeInjectionIds,
        lorebookIds = conversation.lorebookIds,
    )
}

/** 聊天页改动助手后留在会话上的部分，[updated] 是会话视角下改动后的助手。 */
fun Conversation.withAssistantUpdate(updated: Assistant, settings: Settings): Conversation {
    val previous = settings.getAssistantOf(this)
    val config = config
    val conversation = if (config == null) {
        this
    } else {
        copy(
            config = updated.toConversationConfig().copy(
                builtInSearch = if (updated.chatModelId == config.chatModelId) {
                    config.builtInSearch
                } else {
                    // 内置搜索是模型自身的能力，换模型后跟随新模型的开关
                    settings.findModelById(updated.chatModelId)?.tools?.contains(BuiltInTools.Search) == true
                }
            ),
            modeInjectionIds = updated.modeInjectionIds,
            lorebookIds = updated.lorebookIds,
        )
    }
    // 工作目录属于原来的工作区，换工作区后失效
    return if (updated.workspaceId != previous.workspaceId) conversation.copy(workspaceCwd = null) else conversation
}

/** 聊天页改动助手后写回助手设置的部分：会话持有的字段保持 [stored] 的原值。 */
fun Assistant.withoutConversationFields(conversation: Conversation, stored: Assistant): Assistant =
    if (conversation.config == null) {
        this
    } else {
        withConversationConfig(stored.toConversationConfig()).copy(
            modeInjectionIds = stored.modeInjectionIds,
            lorebookIds = stored.lorebookIds,
        )
    }

/** 会话所属助手自身的设置，不含会话上固定的配置；助手被删除后退回当前助手。 */
fun Settings.getStoredAssistantOf(conversation: Conversation): Assistant =
    getAssistantById(conversation.assistantId) ?: getCurrentAssistant()

/** 会话所属的助手（会话视角）。 */
fun Settings.getAssistantOf(conversation: Conversation): Assistant {
    val assistant = getStoredAssistantOf(conversation).withConversation(conversation)
    if (conversation.config == null) return assistant
    // 助手自身的失效引用在读取设置时已清理，会话上固定的这份在这里滤掉
    return assistant.copy(
        mcpServers = assistant.mcpServers.filterTo(mutableSetOf()) { id -> mcpServers.any { it.id == id } },
        modeInjectionIds = assistant.modeInjectionIds
            .filterTo(mutableSetOf()) { id -> modeInjections.any { it.id == id } },
        lorebookIds = assistant.lorebookIds.filterTo(mutableSetOf()) { id -> lorebooks.any { it.id == id } },
    )
}

/** 会话使用的聊天模型；会话开始后内置搜索以会话上固定的开关为准。 */
fun Settings.getChatModelOf(conversation: Conversation): Model? {
    val assistantModel = findModelById(getStoredAssistantOf(conversation).chatModelId ?: chatModelId)
    val config = conversation.config ?: return assistantModel
    // 固定的模型被删除后退回助手当前的模型，内置搜索也跟随该模型自身的开关
    val model = findModelById(config.chatModelId) ?: return assistantModel
    return model.copy(
        tools = if (config.builtInSearch) model.tools + BuiltInTools.Search else model.tools - BuiltInTools.Search
    )
}

/**
 * 把助手当前的配置固定到会话上。已经固定过的会话原样返回，
 * 只有固定的模型被删除时才改为固定助手当前的模型，之后不再跟着助手变。
 */
fun Conversation.bindConfig(settings: Settings): Conversation {
    val model = settings.getChatModelOf(this)
    val builtInSearch = model != null && BuiltInTools.Search in model.tools
    val config = config
    if (config != null) {
        if (model == null || model.id == config.chatModelId) return this
        return copy(config = config.copy(chatModelId = model.id, builtInSearch = builtInSearch))
    }
    val assistant = settings.getAssistantOf(this)
    return copy(
        config = assistant.toConversationConfig().copy(chatModelId = model?.id, builtInSearch = builtInSearch),
        // 旧版本允许会话单独绑定注入，这类会话保留自己的绑定
        modeInjectionIds = modeInjectionIds.ifEmpty { assistant.modeInjectionIds },
        lorebookIds = lorebookIds.ifEmpty { assistant.lorebookIds },
    )
}
'''

applied = []
skipped = []


def joinlist(items):
    t = ''
    for i, s in enumerate(items):
        if i > 0:
            t += ','
        t += s
    return t


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


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


def main():
    # 1. 新建 ConversationConfig.kt
    if (ROOT / NEWFILE).exists():
        applied.append('configfile-exists')
    else:
        write(NEWFILE, CONFIG_KT)
        if 'data class ConversationConfig' not in read(NEWFILE):
            skipped.append('configfile-selfcheck')
        else:
            applied.append('configfile')

    # 2. Conversation.kt 加 config 字段
    conv = read(CONV)
    if conv is None:
        skipped.append('conv-missing')
        print('::error::' + BATCH + ' SKIP conv missing')
        return
    if 'val config: ConversationConfig? = null' in conv:
        applied.append('conv-exists')
    else:
        lines = conv.split(NL)
        bal0 = balance(conv)
        anchor = '    val workspaceCwd: String? = null,'
        hits = [i for i, ln in enumerate(lines) if ln.strip() == 'val workspaceCwd: String? = null,']
        if len(hits) != 1:
            skipped.append('conv-anchor=' + str(len(hits)))
            print('::error::' + BATCH + ' SKIP conv anchor=' + str(len(hits)))
            return
        lines.insert(hits[0] + 1, '    val config: ConversationConfig? = null, // ' + MARK + ' A1地基: 会话级固定配置(A2才落库)')
        out = NL.join(lines)
        if balance(out) != bal0:
            skipped.append('conv-balance')
            print('::error::' + BATCH + ' SKIP conv balance')
            return
        write(CONV, out)
        applied.append('conv-config-field')

    print('::error::' + BATCH + ' applied=[' + joinlist(applied) + '] skipped=[' + joinlist(skipped) + ']')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('::error::' + BATCH + ' crashed: ' + str(exc)[:300])
    sys.exit(0)