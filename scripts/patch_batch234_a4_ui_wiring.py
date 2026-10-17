#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch234: A4 —— 聊天页会话级模型选择器改写 config（收编的写入侧）

上游(rikkahub/rikkahub)做法: ConversationRepository.updateConversationConfig 只更新
  config 列(不重写消息节点); ChatService 用 withAssistantUpdate 把改动留到会话;
  新会话落库时 bindConfig 拍快照。

本批给 fork 接上写入侧:
  1. ConversationDAO.kt: 加 updateConfig(id, config) 单列更新(锚 getAllIdTitles 后,
     batch228 加的—— 锚点取 CI 真形态)。
  2. ConversationRepository.kt: 加 updateConversationConfig(conversation) —— 只写 config 列。
  3. ChatService.kt: 加 setConversationModel(conversationId, modelId) ——
     先 bindConfig 拍快照, 再改 config.chatModelId, 更新 session + 落库 config 列;
     import 补 bindConfig(插在 batch232 加的 getChatModelOf import 后, 注意补换行不再吃掉下行)。
  4. ChatVM.kt: setChatModel 从写助手(assistants.map) 改成调 chatService.setConversationModel
     —— 已落库会话只改自己, 不动助手; 新会话经 bindConfig 走会话。

幂等 marker rhA4SetModel; 各文件锚点唯一; warn-only; 括号差值断言。
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
BATCH = 'batch234'
MARK = 'rhA4SetModel'

DAO = 'app/src/main/java/me/rerere/rikkahub/data/db/dao/ConversationDAO.kt'
REPO = 'app/src/main/java/me/rerere/rikkahub/data/repository/ConversationRepository.kt'
CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'
VM = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatVM.kt'

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
    # ======== 1. ConversationDAO: updateConfig ========
    dao = read(DAO)
    if dao is None:
        skipped.append('dao-missing')
    elif MARK not in dao:
        anchor = '    suspend fun getAllIdTitles(): List<ConversationIdTitle>'
        if dao.count(anchor) == 1:
            new = dao.replace(
                anchor,
                anchor + NL + NL +
                '    /** [batch234] A4: 只更新会话持有的 config 列(不动节点/标题等)。 */' + NL +
                '    @Query("UPDATE conversationentity SET config = :config WHERE id = :id")' + NL +
                '    suspend fun updateConfig(id: String, config: String) // ' + MARK,
                1,
            )
            if balance(new) != balance(dao):
                skipped.append('dao-balance')
            else:
                write(DAO, new)
                applied.append('dao')
        else:
            skipped.append('dao-anchor=' + str(dao.count(anchor)))
    else:
        applied.append('dao-exists')

    # ======== 2. ConversationRepository: updateConversationConfig ========
    repo = read(REPO)
    if repo is None:
        skipped.append('repo-missing')
    elif MARK not in repo:
        anchor = '    suspend fun togglePinStatus(conversationId: Uuid) {'
        if repo.count(anchor) == 1:
            new = repo.replace(
                anchor,
                '    /** [batch234] A4: 只更新会话持有的配置列, 不重写消息节点(防丢)。 */' + NL +
                '    suspend fun updateConversationConfig(conversation: Conversation) {' + NL +
                '        conversationDAO.updateConfig(' + NL +
                '            id = conversation.id.toString(),' + NL +
                '            config = conversation.config?.let { JsonInstant.encodeToString(it) } ?: "",' + NL +
                '        )' + NL +
                '    } // ' + MARK + NL + NL +
                anchor,
                1,
            )
            if balance(new) != balance(repo):
                skipped.append('repo-balance')
            else:
                write(REPO, new)
                applied.append('repo')
        else:
            skipped.append('repo-anchor=' + str(repo.count(anchor)))
    else:
        applied.append('repo-exists')

    # ======== 3. ChatService: import bindConfig + setConversationModel ========
    cs = read(CS)
    if cs is None:
        skipped.append('cs-missing')
    elif MARK not in cs:
        bal0 = balance(cs)
        out = cs
        # 3a. import bindConfig(插在 getChatModelOf import 后; 该行带 // rhA3Wiring 注释, 注意末尾补 NL)
        imp_anchor = 'import me.rerere.rikkahub.data.model.getChatModelOf // rhA3Wiring\n'
        if out.count(imp_anchor) == 1:
            out = out.replace(
                imp_anchor,
                imp_anchor + 'import me.rerere.rikkahub.data.model.bindConfig' + NL,
                1,
            )
            applied.append('cs-import')
        else:
            skipped.append('cs-import-anchor=' + str(out.count(imp_anchor)))
        # 3b. 加 setConversationModel(插在 updateConversationState 前)
        fn_anchor = '    fun updateConversationState(conversationId: Uuid, update: (Conversation) -> Conversation) {'
        if out.count(fn_anchor) == 1:
            out = out.replace(
                fn_anchor,
                '    /** [batch234] A4: 设置当前会话的模型 —— 写会话自己的 config.chatModelId, 不动助手。 */' + NL +
                '    fun setConversationModel(conversationId: Uuid, modelId: Uuid) {' + NL +
                '        val current = getConversationFlow(conversationId).value' + NL +
                '        val bound = current.bindConfig(settingsStore.settingsFlow.value)' + NL +
                '        val updated = bound.copy(config = bound.config?.copy(chatModelId = modelId))' + NL +
                '        updateConversation(conversationId, updated)' + NL +
                '        conversationRepo.updateConversationConfig(updated)' + NL +
                '    } // ' + MARK + NL + NL +
                fn_anchor,
                1,
            )
            applied.append('cs-fn')
        else:
            skipped.append('cs-fn-anchor=' + str(out.count(fn_anchor)))
        if 'cs-import' in applied and 'cs-fn' in applied:
            if balance(out) != bal0:
                skipped.append('cs-balance')
            else:
                write(CS, out)
    else:
        applied.append('cs-exists')

    # ======== 4. ChatVM: setChatModel 改走会话级 ========
    vm = read(VM)
    if vm is None:
        skipped.append('vm-missing')
    elif MARK not in vm:
        old_fn = '''    fun setChatModel(assistant: Assistant, model: Model) {
        viewModelScope.launch {
            settingsStore.update { settings ->
                settings.copy(
                    assistants = settings.assistants.map {
                        if (it.id == assistant.id) {
                            it.copy(
                                chatModelId = model.id
                            )
                        } else {
                            it
                        }
                    })
            }
        }
    }'''
        new_fn = '''    fun setChatModel(assistant: Assistant, model: Model) {
        viewModelScope.launch {
            // [batch234] A4: 写当前会话自己的 config.chatModelId, 不动助手(会话级)
            chatService.setConversationModel(_conversationId, model.id)
        }
    }'''
        if vm.count(old_fn) == 1:
            new = vm.replace(old_fn, new_fn, 1)
            if balance(new) != balance(vm):
                skipped.append('vm-balance')
            else:
                write(VM, new)
                applied.append('vm')
        else:
            skipped.append('vm-anchor=' + str(vm.count(old_fn)))
    else:
        applied.append('vm-exists')

    print('::error::' + BATCH + ' applied=[' + joinlist(applied) + '] skipped=[' + joinlist(skipped) + ']')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('::error::' + BATCH + ' crashed: ' + str(exc)[:300])
    sys.exit(0)