#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch231: 短期记忆 UI 层 — 双开关互斥 + 管理页按会话分组

依赖 batch230(先合入): MemoryRepository.getSessionMemoriesOfAssistantFlow /
addMemory(conversationId) / Assistant.enableShortMemory / AssistantMemory.conversationId。

改动(5 文件):
1. AssistantDetailVM.kt: +conversationRepository 构造参数; memories flow 短期分支;
   +conversationTitles(分组标题映射); addMemory 短期路由
2. ViewModelModule.kt: AssistantDetailVM 注册 +conversationRepository = get()
3. AssistantMemoryPage.kt: 长期/短期双开关互斥; 短期模式按会话分组渲染(组头带添加按钮);
   顶部全局添加按钮短期模式隐藏
4. values/strings.xml: assistant_page_memory 值改 Long-term memory; desc 更新; +4 新键
5. values-zh/strings.xml: 同步中文

互斥实现: UI 开关互相挤掉(开长期→关短期; 开短期→关长期+全局);
消费侧(batch230)短期优先兜底, 双开脏数据行为确定。

五查:
1. import 清单: AssistantDetailVM +ConversationRepository; Page/Module/strings 无新 import
2. 同文件冲突: 四个目标文件 snapshot 与仓库态 SHA 相同(无在链 patch); ViewModelModule 锚点取自 snapshot 实读
3. 作用域: conversationTitles 参数 Page→Content 传递; VM 内 conversationRepository 为构造注入
4. 括号配对: 每文件改后 balance 自检
5. 函数签名: VM 构造参数加在最后(koin get() 按类型注入); Page 内部函数加参数, 调用点同步

Python 三查: Q/SQ/NL 变量构造; 无 f-string/join/walrus; 失败 exit(0)+::error
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
SQ = chr(39)
MARK = 'rhShortMemUI'


def fail(msg):
    print('::error::batch231 ' + str(msg)[:1400])
    sys.stdout.flush()
    sys.exit(0)


def balance(text):
    return (text.count('(') - text.count(')')
            + text.count('{') - text.count('}')
            + text.count('[') - text.count(']'))


def load(rel):
    p = ROOT / rel
    if not p.exists():
        fail('file missing: ' + rel)
    return p.read_text(encoding='utf-8')


def save(rel, text):
    (ROOT / rel).write_text(text, encoding='utf-8')


def replace_once(text, old, new, label):
    n = text.count(old)
    if n == 0:
        fail(label + ': anchor not found. head=' + repr(old[:120]))
    if n != 1:
        fail(label + ': anchor count=' + str(n) + ' (expected 1). head=' + repr(old[:120]))
    return text.replace(old, new, 1)


def replace_line_starting(text, prefix, new_content, label):
    # 整行替换: 找 strip 后以 prefix 开头的唯一行, 保留缩进替换内容. 不用 join.
    lines = text.split(NL)
    hits = []
    for i, ln in enumerate(lines):
        if ln.strip().startswith(prefix):
            hits.append(i)
    if len(hits) != 1:
        fail(label + ': line anchor count=' + str(len(hits)) + ' prefix=' + prefix[:60])
    idx = hits[0]
    old_line = lines[idx]
    indent = old_line[:len(old_line) - len(old_line.lstrip())]
    lines[idx] = indent + new_content
    out = ''
    for i, ln in enumerate(lines):
        if i > 0:
            out += NL
        out += ln
    return out


def patch_vm():
    rel = 'app/src/main/java/me/rerere/rikkahub/ui/pages/assistant/detail/AssistantDetailVM.kt'
    t = load(rel)
    if MARK in t:
        print('batch231: ' + rel + ' already applied')
        return
    bal0 = balance(t)

    old_imp = 'import me.rerere.rikkahub.data.repository.MemoryRepository'
    new_imp = ('import me.rerere.rikkahub.data.repository.ConversationRepository // ' + MARK + NL
               + old_imp)
    t = replace_once(t, old_imp, new_imp, 'VM import')

    old_ctor = ('    private val workspaceRepository: WorkspaceRepository,' + NL
                + ') : ViewModel() {')
    new_ctor = ('    private val workspaceRepository: WorkspaceRepository,' + NL
                + '    private val conversationRepository: ConversationRepository, // ' + MARK + NL
                + ') : ViewModel() {')
    t = replace_once(t, old_ctor, new_ctor, 'VM ctor')

    old_flow = ('    val memories = assistant' + NL
                + '        .flatMapLatest { currentAssistant ->' + NL
                + '            if (currentAssistant.useGlobalMemory) {' + NL
                + '                memoryRepository.getGlobalMemoriesFlow()' + NL
                + '            } else {' + NL
                + '                memoryRepository.getMemoriesOfAssistantFlow(assistantId.toString())' + NL
                + '            }' + NL
                + '        }')
    new_flow = ('    val memories = assistant' + NL
                + '        .flatMapLatest { currentAssistant ->' + NL
                + '            // ' + MARK + ': 短期模式列出该助手全部会话的记忆, UI 按会话分组' + NL
                + '            if (currentAssistant.enableShortMemory) {' + NL
                + '                memoryRepository.getSessionMemoriesOfAssistantFlow(assistantId.toString())' + NL
                + '            } else if (currentAssistant.useGlobalMemory) {' + NL
                + '                memoryRepository.getGlobalMemoriesFlow()' + NL
                + '            } else {' + NL
                + '                memoryRepository.getMemoriesOfAssistantFlow(assistantId.toString())' + NL
                + '            }' + NL
                + '        }')
    t = replace_once(t, old_flow, new_flow, 'VM memories flow')

    old_next = '    val providers = settingsStore'
    new_titles = ('    // ' + MARK + ': 短期记忆管理页的会话标题映射(conversationId -> title)' + NL
                  + '    val conversationTitles = conversationRepository' + NL
                  + '        .getConversationsOfAssistant(assistantId)' + NL
                  + '        .map { list -> list.associate { it.id.toString() to it.title } }' + NL
                  + '        .stateIn(' + NL
                  + '            scope = viewModelScope, started = SharingStarted.Eagerly, initialValue = emptyMap()' + NL
                  + '        )' + NL
                  + NL)
    t = replace_once(t, old_next, new_titles + old_next, 'VM conversationTitles')

    old_add = ('            val memoryAssistantId = if (assistant.value.useGlobalMemory) {' + NL
               + '                MemoryRepository.GLOBAL_MEMORY_ID' + NL
               + '            } else {' + NL
               + '                assistantId.toString()' + NL
               + '            }' + NL
               + '            memoryRepository.addMemory(' + NL
               + '                assistantId = memoryAssistantId,' + NL
               + '                content = memory.content' + NL
               + '            )')
    new_add = ('            // ' + MARK + ': 短期模式跳过全局开关, 记忆归属调用方指定的会话' + NL
               + '            val shortMode = assistant.value.enableShortMemory' + NL
               + '            val memoryAssistantId = if (assistant.value.useGlobalMemory && !shortMode) {' + NL
               + '                MemoryRepository.GLOBAL_MEMORY_ID' + NL
               + '            } else {' + NL
               + '                assistantId.toString()' + NL
               + '            }' + NL
               + '            memoryRepository.addMemory(' + NL
               + '                assistantId = memoryAssistantId,' + NL
               + '                content = memory.content,' + NL
               + '                conversationId = if (shortMode) memory.conversationId else ' + Q + Q + NL
               + '            )')
    t = replace_once(t, old_add, new_add, 'VM addMemory')

    if balance(t) != bal0:
        fail('VM: balance changed')
    if t.count('getSessionMemoriesOfAssistantFlow') != 1:
        fail('VM: session flow wire missing')
    save(rel, t)
    print('batch231: AssistantDetailVM OK')


def patch_module():
    rel = 'app/src/main/java/me/rerere/rikkahub/di/ViewModelModule.kt'
    t = load(rel)
    if MARK in t:
        print('batch231: ' + rel + ' already applied')
        return
    bal0 = balance(t)
    old = ('            skillManager = get(),' + NL
           + '            workspaceRepository = get(),' + NL
           + '        )' + NL
           + '    }')
    new = ('            skillManager = get(),' + NL
           + '            workspaceRepository = get(),' + NL
           + '            conversationRepository = get(), // ' + MARK + NL
           + '        )' + NL
           + '    }')
    t = replace_once(t, old, new, 'ViewModelModule')
    if balance(t) != bal0:
        fail('ViewModelModule: balance changed')
    save(rel, t)
    print('batch231: ViewModelModule OK')


def patch_page():
    rel = 'app/src/main/java/me/rerere/rikkahub/ui/pages/assistant/detail/AssistantMemoryPage.kt'
    t = load(rel)
    if MARK in t:
        print('batch231: ' + rel + ' already applied')
        return
    bal0 = balance(t)

    old_collect = '    val memories by vm.memories.collectAsStateWithLifecycle()'
    new_collect = (old_collect + NL
                   + '    val conversationTitles by vm.conversationTitles.collectAsStateWithLifecycle() // ' + MARK)
    t = replace_once(t, old_collect, new_collect, 'Page collect')

    old_call = ('        AssistantMemoryContent(' + NL
                + '            innerPadding = innerPadding,' + NL
                + '            assistant = assistant,' + NL
                + '            memories = memories,')
    new_call = ('        AssistantMemoryContent(' + NL
                + '            innerPadding = innerPadding,' + NL
                + '            assistant = assistant,' + NL
                + '            memories = memories,' + NL
                + '            conversationTitles = conversationTitles, // ' + MARK)
    t = replace_once(t, old_call, new_call, 'Page call')

    old_sig = ('private fun AssistantMemoryContent(' + NL
               + '    innerPadding: PaddingValues,' + NL
               + '    assistant: Assistant,' + NL
               + '    memories: List<AssistantMemory>,')
    new_sig = ('private fun AssistantMemoryContent(' + NL
               + '    innerPadding: PaddingValues,' + NL
               + '    assistant: Assistant,' + NL
               + '    memories: List<AssistantMemory>,' + NL
               + '    conversationTitles: Map<String, String>, // ' + MARK)
    t = replace_once(t, old_sig, new_sig, 'Page signature')

    old_sw = ('                        checked = assistant.enableMemory,' + NL
              + '                        onCheckedChange = {' + NL
              + '                            onUpdateAssistant(' + NL
              + '                                assistant.copy(' + NL
              + '                                    enableMemory = it' + NL
              + '                                )' + NL
              + '                            )' + NL
              + '                        }')
    new_sw = ('                        checked = assistant.enableMemory,' + NL
              + '                        onCheckedChange = {' + NL
              + '                            onUpdateAssistant(' + NL
              + '                                assistant.copy(' + NL
              + '                                    // ' + MARK + ': 长期/短期互斥' + NL
              + '                                    enableMemory = it,' + NL
              + '                                    enableShortMemory = if (it) false else assistant.enableShortMemory' + NL
              + '                                )' + NL
              + '                            )' + NL
              + '                        }')
    t = replace_once(t, old_sw, new_sw, 'Page long-memory switch')

    old_global = ('            item(' + NL
                  + '                headlineContent = { Text(stringResource(R.string.assistant_page_global_memory)) },')
    new_short = ('            // ' + MARK + ': 短期记忆(会话私有), 与长期记忆互斥' + NL
                 + '            item(' + NL
                 + '                headlineContent = { Text(stringResource(R.string.assistant_page_short_memory)) },' + NL
                 + '                supportingContent = {' + NL
                 + '                    Text(' + NL
                 + '                        text = stringResource(R.string.assistant_page_short_memory_desc),' + NL
                 + '                    )' + NL
                 + '                },' + NL
                 + '                trailingContent = {' + NL
                 + '                    Switch(' + NL
                 + '                        checked = assistant.enableShortMemory,' + NL
                 + '                        onCheckedChange = {' + NL
                 + '                            onUpdateAssistant(' + NL
                 + '                                assistant.copy(' + NL
                 + '                                    enableShortMemory = it,' + NL
                 + '                                    enableMemory = if (it) false else assistant.enableMemory,' + NL
                 + '                                    useGlobalMemory = if (it) false else assistant.useGlobalMemory' + NL
                 + '                                )' + NL
                 + '                            )' + NL
                 + '                        }' + NL
                 + '                    )' + NL
                 + '                }' + NL
                 + '            )' + NL)
    t = replace_once(t, old_global, new_short + old_global, 'Page short-memory item')

    old_box = ('        Box(' + NL
               + '            modifier = Modifier' + NL
               + '                .fillMaxWidth()' + NL
               + '                .padding(horizontal = 8.dp)' + NL
               + '        ) {' + NL
               + '            Text(' + NL
               + '                text = stringResource(R.string.assistant_page_manage_memory_title),' + NL
               + '                style = MaterialTheme.typography.titleMedium,' + NL
               + '                modifier = Modifier' + NL
               + '                    .padding(bottom = 8.dp)' + NL
               + '                    .align(Alignment.CenterStart)' + NL
               + '            )' + NL
               + NL
               + '            IconButton(' + NL
               + '                onClick = {' + NL
               + '                    memoryDialogState.open(AssistantMemory(0, ' + Q + Q + '))' + NL
               + '                },' + NL
               + '                modifier = Modifier.align(Alignment.CenterEnd)' + NL
               + '            ) {' + NL
               + '                Icon(' + NL
               + '                    imageVector = HugeIcons.Add01,' + NL
               + '                    contentDescription = null' + NL
               + '                )' + NL
               + '            }' + NL
               + '        }')
    new_box = ('        Box(' + NL
               + '            modifier = Modifier' + NL
               + '                .fillMaxWidth()' + NL
               + '                .padding(horizontal = 8.dp)' + NL
               + '        ) {' + NL
               + '            Text(' + NL
               + '                text = stringResource(R.string.assistant_page_manage_memory_title),' + NL
               + '                style = MaterialTheme.typography.titleMedium,' + NL
               + '                modifier = Modifier' + NL
               + '                    .padding(bottom = 8.dp)' + NL
               + '                    .align(Alignment.CenterStart)' + NL
               + '            )' + NL
               + NL
               + '            // ' + MARK + ': 短期记忆必须归属具体会话, 顶部全局添加按钮隐藏(各组有自己的添加按钮)' + NL
               + '            if (!assistant.enableShortMemory) {' + NL
               + '                IconButton(' + NL
               + '                    onClick = {' + NL
               + '                        memoryDialogState.open(AssistantMemory(0, ' + Q + Q + '))' + NL
               + '                    },' + NL
               + '                    modifier = Modifier.align(Alignment.CenterEnd)' + NL
               + '                ) {' + NL
               + '                    Icon(' + NL
               + '                        imageVector = HugeIcons.Add01,' + NL
               + '                        contentDescription = null' + NL
               + '                    )' + NL
               + '                }' + NL
               + '            }' + NL
               + '        }')
    t = replace_once(t, old_box, new_box, 'Page add button')

    old_list = ('        memories.fastForEach { memory ->' + NL
                + '            key(memory.id) {' + NL
                + '                MemoryItem(' + NL
                + '                    memory = memory,' + NL
                + '                    onEditMemory = {' + NL
                + '                        memoryDialogState.open(it)' + NL
                + '                    },' + NL
                + '                    onDeleteMemory = {' + NL
                + '                        pendingDeleteMemory = it' + NL
                + '                    }' + NL
                + '                )' + NL
                + '            }' + NL
                + '        }')
    new_list = ('        if (assistant.enableShortMemory) {' + NL
                + '            // ' + MARK + ': 短期记忆按会话分组' + NL
                + '            val groupedShortMemories = memories.groupBy { it.conversationId }' + NL
                + '            if (groupedShortMemories.isEmpty()) {' + NL
                + '                Text(' + NL
                + '                    text = stringResource(R.string.assistant_page_short_memory_empty),' + NL
                + '                    style = MaterialTheme.typography.bodySmall,' + NL
                + '                    color = MaterialTheme.colorScheme.onSurfaceVariant,' + NL
                + '                    modifier = Modifier.padding(8.dp)' + NL
                + '                )' + NL
                + '            }' + NL
                + '            groupedShortMemories.forEach { (convId, convMemories) ->' + NL
                + '                Row(' + NL
                + '                    modifier = Modifier' + NL
                + '                        .fillMaxWidth()' + NL
                + '                        .padding(horizontal = 8.dp),' + NL
                + '                    verticalAlignment = Alignment.CenterVertically' + NL
                + '                ) {' + NL
                + '                    Text(' + NL
                + '                        text = conversationTitles[convId] ?: stringResource(R.string.assistant_page_memory_unknown_conversation),' + NL
                + '                        style = MaterialTheme.typography.titleSmall,' + NL
                + '                        maxLines = 1,' + NL
                + '                        overflow = TextOverflow.Ellipsis,' + NL
                + '                        modifier = Modifier.weight(1f)' + NL
                + '                    )' + NL
                + '                    IconButton(' + NL
                + '                        onClick = {' + NL
                + '                            memoryDialogState.open(AssistantMemory(0, ' + Q + Q + ', convId))' + NL
                + '                        }' + NL
                + '                    ) {' + NL
                + '                        Icon(HugeIcons.Add01, null)' + NL
                + '                    }' + NL
                + '                }' + NL
                + '                convMemories.fastForEach { memory ->' + NL
                + '                    key(memory.id) {' + NL
                + '                        MemoryItem(' + NL
                + '                            memory = memory,' + NL
                + '                            onEditMemory = {' + NL
                + '                                memoryDialogState.open(it)' + NL
                + '                            },' + NL
                + '                            onDeleteMemory = {' + NL
                + '                                pendingDeleteMemory = it' + NL
                + '                            }' + NL
                + '                        )' + NL
                + '                    }' + NL
                + '                }' + NL
                + '            }' + NL
                + '        } else {' + NL
                + '            memories.fastForEach { memory ->' + NL
                + '                key(memory.id) {' + NL
                + '                    MemoryItem(' + NL
                + '                        memory = memory,' + NL
                + '                        onEditMemory = {' + NL
                + '                            memoryDialogState.open(it)' + NL
                + '                        },' + NL
                + '                        onDeleteMemory = {' + NL
                + '                            pendingDeleteMemory = it' + NL
                + '                        }' + NL
                + '                    )' + NL
                + '                }' + NL
                + '            }' + NL
                + '        }')
    t = replace_once(t, old_list, new_list, 'Page list')

    if balance(t) != bal0:
        fail('Page: balance changed')
    if t.count('assistant_page_short_memory') < 2:
        fail('Page: short-memory string refs missing')
    save(rel, t)
    print('batch231: AssistantMemoryPage OK')


def patch_strings():
    rel_en = 'app/src/main/res/values/strings.xml'
    t = load(rel_en)
    if MARK not in t:
        t = replace_line_starting(
            t,
            '<string name=' + Q + 'assistant_page_memory' + Q + '>',
            '<string name=' + Q + 'assistant_page_memory' + Q + '>Long-term memory</string>',
            'strings en memory title')
        t = replace_line_starting(
            t,
            '<string name=' + Q + 'assistant_page_memory_desc' + Q + '>',
            '<string name=' + Q + 'assistant_page_memory_desc' + Q + '>Long-term memory is shared across all conversations of this assistant. This feature requires the model to support tool calls to work properly</string>',
            'strings en memory desc')
        new_keys = ('  <!-- ' + MARK + ' -->' + NL
                    + '  <string name=' + Q + 'assistant_page_short_memory' + Q + '>Short-term memory</string>' + NL
                    + '  <string name=' + Q + 'assistant_page_short_memory_desc' + Q + '>Short-term memory is private to each conversation: memories are only visible within the conversation where they were created. Cannot be enabled together with long-term memory.</string>' + NL
                    + '  <string name=' + Q + 'assistant_page_short_memory_empty' + Q + '>No short-term memories yet. Memories the AI saves in each conversation appear here, grouped by conversation.</string>' + NL
                    + '  <string name=' + Q + 'assistant_page_memory_unknown_conversation' + Q + '>Unknown conversation</string>' + NL)
        t = replace_once(t, '</resources>', new_keys + '</resources>', 'strings en append')
        save(rel_en, t)
        print('batch231: strings en OK')
    else:
        print('batch231: strings en already applied')

    rel_zh = 'app/src/main/res/values-zh/strings.xml'
    tz = load(rel_zh)
    if MARK not in tz:
        tz = replace_line_starting(
            tz,
            '<string name=' + Q + 'assistant_page_memory' + Q + '>',
            '<string name=' + Q + 'assistant_page_memory' + Q + '>长期记忆</string>',
            'strings zh memory title')
        tz = replace_line_starting(
            tz,
            '<string name=' + Q + 'assistant_page_memory_desc' + Q + '>',
            '<string name=' + Q + 'assistant_page_memory_desc' + Q + '>长期记忆在该助手下的所有会话之间共享（公共）。此功能需要模型支持工具调用才能正常工作</string>',
            'strings zh memory desc')
        new_keys_zh = ('  <!-- ' + MARK + ' -->' + NL
                       + '  <string name=' + Q + 'assistant_page_short_memory' + Q + '>短期记忆</string>' + NL
                       + '  <string name=' + Q + 'assistant_page_short_memory_desc' + Q + '>短期记忆是每个会话私有的：记忆仅在创建它的会话中可见，会话之间互不可见。不能与长期记忆同时开启。</string>' + NL
                       + '  <string name=' + Q + 'assistant_page_short_memory_empty' + Q + '>暂无短期记忆。AI 在各会话中保存的记忆会按会话分组显示在这里。</string>' + NL
                       + '  <string name=' + Q + 'assistant_page_memory_unknown_conversation' + Q + '>未知会话</string>' + NL)
        tz = replace_once(tz, '</resources>', new_keys_zh + '</resources>', 'strings zh append')
        save(rel_zh, tz)
        print('batch231: strings zh OK')
    else:
        print('batch231: strings zh already applied')


def main():
    patch_vm()
    patch_module()
    patch_page()
    patch_strings()
    print('::notice::batch231 OK - short-memory UI: mutex switches + per-conversation grouped management')


main()
