#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch240: 短期/长期记忆 UI 精致化 + 工具调用介绍按当前使用中模式独立展示

用户要求:
  「一定要精致好用 UI可观, 并且短期记忆和长期记忆要有工具调用介绍来区别 只显示使用中的就行」

改动(3 文件):
  1. MemoryTools.kt (整文件重写, 95 行自包含):
     - sessionScoped=true(短期记忆) 与 false(长期记忆) 使用完全独立的两套工具描述,
       短期模式只显示会话私有(SHORT-TERM / THIS conversation only)介绍, 绝不混入长期记忆描述;
       长期模式只显示跨会话共享(LONG-TERM / across all conversations)介绍。
     - delete 动作返回 JSON 附带 scope="short"|"long", 供聊天 UI 区分。
  2. BuiltinToolUIs.kt (MemoryToolUI):
     - 聊天消息中的 memory_tool 工具调用卡片标题根据 conversationId / scope 自动区分显示:
       「写入短期记忆 / 更新短期记忆 / 删除短期记忆」 vs 「写入长期记忆 / 更新长期记忆 / 删除长期记忆」。
  3. AssistantMemoryPage.kt (整文件重写, 仅被我方 batch231 改过):
     - 开关组下方新增「当前生效的工具调用介绍」卡片 —— 只显示当前开启的那一个模式
       (开长期只展示长期记忆 memory_tool 介绍, 开短期只展示短期记忆 memory_tool 介绍, 均关则不显示)。
     - 短期记忆按会话分组升级为可折叠圆角分组卡片(含会话图标、会话标题、N 条胶囊徽标、
       组内快捷 + 按钮、折叠/展开切换)。
     - 顶部「管理记忆」栏显示总条数胶囊徽标, 并保留顶部 + 按钮; 短期模式下新建记忆时弹窗内
       提供会话选择芯片(解决此前短期记忆为空时无法手动新增的 UX 死角)。

五查:
1. import 清单:
   - MemoryTools.kt / AssistantMemoryPage.kt 整文件重写, import 逐一对照 ChatList.kt/BuiltinToolUIs.kt 已证实存在;
   - BuiltinToolUIs.kt 零新增 import。
2. 同文件冲突:
   - MemoryTools.kt / AssistantMemoryPage.kt 仅被我方 230/231 修改, 本批在 230/231 之后运行;
   - BuiltinToolUIs.kt 无在链 patch 修改 MemoryToolUI.title。
3. 作用域: 各组件内部状态自包含。
4. 括号配对: 逐文件校验 balance == 0。
5. 函数签名: buildMemoryTools / AssistantMemoryPage 签名保持兼容。

Python 三查: 三引号块与 Q 变量构造; NL 手写 concat 禁 f-string/join/walrus; helper 先定义后用; fail-loud
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhMemPolish240'

TOOLS = 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/MemoryTools.kt'
BUILTIN_UI = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/tools/BuiltinToolUIs.kt'
PAGE = 'app/src/main/java/me/rerere/rikkahub/ui/pages/assistant/detail/AssistantMemoryPage.kt'


def fail(msg):
    print('::error::batch240 ' + str(msg)[:1400])
    sys.stdout.flush()
    sys.exit(0)


def balance(text):
    return (text.count('(') - text.count(')')
            + text.count('{') - text.count('}')
            + text.count('[') - text.count(']'))


def replace_once(text, old, new, label):
    n = text.count(old)
    if n == 0:
        fail(label + ': anchor not found. head=' + repr(old[:120]))
    if n != 1:
        fail(label + ': anchor count=' + str(n) + ' (expected 1). head=' + repr(old[:120]))
    return text.replace(old, new, 1)


TOOLS_CODE = '''package me.rerere.rikkahub.data.ai.tools

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.add
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import me.rerere.ai.core.InputSchema
import me.rerere.ai.core.Tool
import me.rerere.ai.ui.UIMessagePart
import me.rerere.rikkahub.data.model.AssistantMemory
import me.rerere.rikkahub.utils.toLocalString
import java.time.LocalDate

// rhShortMem + rhMemPolish240: 短期记忆与长期记忆使用完全独立的两套工具介绍, 只向模型暴露当前开启的那一种
fun buildMemoryTools(
    json: Json,
    sessionScoped: Boolean = false,
    onCreation: suspend (String) -> AssistantMemory,
    onUpdate: suspend (Int, String) -> AssistantMemory,
    onDelete: suspend (Int) -> Unit
): List<Tool> = listOf(
    Tool(
        name = "memory_tool",
        description = if (sessionScoped) {
            """
                [SHORT-TERM MEMORY — CURRENT CONVERSATION ONLY]
                The memory tool stores short-term context and notes private to THIS conversation only.
                Use `action` to control the operation: `create` (add), `edit` (update), `delete` (remove).
                - No relevant record: `create` + `content`
                - Existing relevant record: `edit` + `id` + `content`
                - Outdated/irrelevant record: `delete` + `id`
                Short-term memories automatically appear in the <memories> tag within THIS conversation only, and are NEVER shared with other conversations.
                You may store: current session goals, temporary constraints, progress notes, or roleplay state specific to this chat.
                Do not show memory content directly in the conversation unless the user explicitly asks.
                Today is ${LocalDate.now().toLocalString(true)}.
                Similar memories should be merged; prefer updating existing records.

                Examples:
                {"action":"create","content":"In this conversation, user wants concise code-only answers."}
                {"action":"edit","id":12,"content":"Current session task updated to refactoring the backup dialog."}
                {"action":"delete","id":7}
            """.trimIndent()
        } else {
            """
                [LONG-TERM MEMORY — SHARED ACROSS CONVERSATIONS]
                The memory tool stores long-term information shared across all conversations of this assistant.
                Use `action` to control the operation: `create` (add), `edit` (update), `delete` (remove).
                - No relevant record: `create` + `content`
                - Existing relevant record: `edit` + `id` + `content`
                - Outdated/irrelevant record: `delete` + `id`
                Long-term memories automatically appear in the <memories> tag in all future conversations.
                Do not store sensitive information (e.g., ethnicity, religion, sexual orientation, political views, sex life, criminal records).
                You may store: preferred name, preferences, plans, work-related notes, chat style preferences, first chat time, etc.
                Do not show memory content directly in the conversation unless the user explicitly asks.
                Today is ${LocalDate.now().toLocalString(true)}.
                Similar memories should be merged; prefer updating existing records.

                Examples:
                {"action":"create","content":"User prefers brief replies and is more active on weekends."}
                {"action":"edit","id":12,"content":"User’s preferred name updated to “A-Xing”, prefers Chinese replies."}
                {"action":"delete","id":7}
            """.trimIndent()
        },
        parameters = {
            InputSchema.Obj(
                properties = buildJsonObject {
                    put("action", buildJsonObject {
                        put("type", "string")
                        put(
                            "enum",
                            buildJsonArray {
                                add("create")
                                add("edit")
                                add("delete")
                            }
                        )
                        put("description", "Operation to perform: create, edit, or delete")
                    })
                    put("id", buildJsonObject {
                        put("type", "integer")
                        put("description", "The id of the memory record (required for edit/delete)")
                    })
                    put("content", buildJsonObject {
                        put("type", "string")
                        put("description", "The content of the memory record (required for create/edit)")
                    })
                },
                required = listOf("action")
            )
        },
        execute = {
            val params = it.jsonObject
            val action = params["action"]?.jsonPrimitive?.contentOrNull ?: error("action is required")
            val payload = when (action) {
                "create" -> {
                    val content = params["content"]?.jsonPrimitive?.contentOrNull ?: error("content is required")
                    json.encodeToJsonElement(AssistantMemory.serializer(), onCreation(content))
                }

                "edit" -> {
                    val id = params["id"]?.jsonPrimitive?.intOrNull ?: error("id is required")
                    val content = params["content"]?.jsonPrimitive?.contentOrNull ?: error("content is required")
                    json.encodeToJsonElement(AssistantMemory.serializer(), onUpdate(id, content))
                }

                "delete" -> {
                    val id = params["id"]?.jsonPrimitive?.intOrNull ?: error("id is required")
                    onDelete(id)
                    buildJsonObject {
                        put("success", true)
                        put("id", id)
                        put("scope", if (sessionScoped) "short" else "long")
                    }
                }

                else -> error("unknown action: $action, must be one of [create, edit, delete]")
            }
            listOf(UIMessagePart.Text(payload.toString()))
        }
    )
)
'''


PAGE_CODE = '''package me.rerere.rikkahub.ui.pages.assistant.detail

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LargeFlexibleTopAppBar
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.util.fastForEach
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import me.rerere.hugeicons.HugeIcons
import me.rerere.hugeicons.stroke.Add01
import me.rerere.hugeicons.stroke.ArrowDown01
import me.rerere.hugeicons.stroke.ArrowUp01
import me.rerere.hugeicons.stroke.Delete01
import me.rerere.hugeicons.stroke.Message02
import me.rerere.hugeicons.stroke.PencilEdit01
import me.rerere.hugeicons.stroke.QuillWrite01
import me.rerere.rikkahub.R
import me.rerere.rikkahub.data.model.Assistant
import me.rerere.rikkahub.data.model.AssistantMemory
import me.rerere.rikkahub.ui.components.nav.BackButton
import me.rerere.rikkahub.ui.components.ui.CardGroup
import me.rerere.rikkahub.ui.components.ui.RikkaConfirmDialog
import me.rerere.rikkahub.ui.hooks.EditStateContent
import me.rerere.rikkahub.ui.hooks.useEditState
import me.rerere.rikkahub.ui.theme.CustomColors
import org.koin.androidx.compose.koinViewModel
import org.koin.core.parameter.parametersOf

// rhShortMemUI + rhMemPolish240: 精致化记忆管理页 + 工具调用介绍卡(只显示使用中的那一个)
@Composable
fun AssistantMemoryPage(id: String) {
    val vm: AssistantDetailVM = koinViewModel(
        parameters = {
            parametersOf(id)
        }
    )
    val assistant by vm.assistant.collectAsStateWithLifecycle()
    val memories by vm.memories.collectAsStateWithLifecycle()
    val conversationTitles by vm.conversationTitles.collectAsStateWithLifecycle() // rhShortMemUI
    val scrollBehavior = TopAppBarDefaults.exitUntilCollapsedScrollBehavior()

    Scaffold(
        topBar = {
            LargeFlexibleTopAppBar(
                title = {
                    Text(stringResource(R.string.assistant_page_tab_memory))
                },
                navigationIcon = {
                    BackButton()
                },
                scrollBehavior = scrollBehavior,
                colors = CustomColors.topBarColors,
            )
        },
        modifier = Modifier.nestedScroll(scrollBehavior.nestedScrollConnection),
        containerColor = CustomColors.topBarColors.containerColor,
    ) { innerPadding ->
        AssistantMemoryContent(
            innerPadding = innerPadding,
            assistant = assistant,
            memories = memories,
            conversationTitles = conversationTitles,
            onUpdateAssistant = { vm.update(it) },
            onDeleteMemory = { vm.deleteMemory(it) },
            onAddMemory = { vm.addMemory(it) },
            onUpdateMemory = { vm.updateMemory(it) }
        )
    }
}

@Composable
private fun AssistantMemoryContent(
    innerPadding: PaddingValues,
    assistant: Assistant,
    memories: List<AssistantMemory>,
    conversationTitles: Map<String, String>,
    onUpdateAssistant: (Assistant) -> Unit,
    onAddMemory: (AssistantMemory) -> Unit,
    onUpdateMemory: (AssistantMemory) -> Unit,
    onDeleteMemory: (AssistantMemory) -> Unit,
) {
    val memoryDialogState = useEditState<AssistantMemory> {
        if (it.id == 0) {
            onAddMemory(it)
        } else {
            onUpdateMemory(it)
        }
    }
    var pendingDeleteMemory by remember { mutableStateOf<AssistantMemory?>(null) }
    val collapsedGroups = remember { mutableStateMapOf<String, Boolean>() }

    // 记忆编辑/新建对话框(短期模式新建时支持选择归属会话)
    memoryDialogState.EditStateContent { memory, update ->
        AlertDialog(
            onDismissRequest = {
                memoryDialogState.dismiss()
            },
            title = {
                Text(
                    if (memory.id == 0) {
                        if (assistant.enableShortMemory) "添加短期记忆" else "添加长期记忆"
                    } else {
                        stringResource(R.string.assistant_page_manage_memory_title)
                    }
                )
            },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    if (assistant.enableShortMemory && memory.id == 0 && conversationTitles.isNotEmpty()) {
                        Text(
                            text = "归属会话",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .horizontalScroll(rememberScrollState()),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            conversationTitles.entries.take(15).forEach { (cid, title) ->
                                FilterChip(
                                    selected = memory.conversationId == cid,
                                    onClick = { update(memory.copy(conversationId = cid)) },
                                    label = {
                                        Text(
                                            text = title.ifBlank { "未命名会话" },
                                            maxLines = 1,
                                            overflow = TextOverflow.Ellipsis,
                                        )
                                    },
                                )
                            }
                        }
                    } else if (assistant.enableShortMemory && memory.conversationId.isNotBlank()) {
                        Surface(
                            shape = RoundedCornerShape(8.dp),
                            color = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.6f),
                        ) {
                            Row(
                                modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(6.dp),
                            ) {
                                Icon(
                                    imageVector = HugeIcons.Message02,
                                    contentDescription = null,
                                    modifier = Modifier.size(14.dp),
                                    tint = MaterialTheme.colorScheme.onSecondaryContainer,
                                )
                                Text(
                                    text = conversationTitles[memory.conversationId]?.ifBlank { null }
                                        ?: stringResource(R.string.assistant_page_memory_unknown_conversation),
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSecondaryContainer,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                )
                            }
                        }
                    }
                    OutlinedTextField(
                        value = memory.content,
                        onValueChange = {
                            update(memory.copy(content = it))
                        },
                        label = {
                            Text(stringResource(R.string.assistant_page_manage_memory_title))
                        },
                        modifier = Modifier.fillMaxWidth(),
                        minLines = 3,
                        maxLines = 8,
                    )
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        memoryDialogState.confirm()
                    },
                    enabled = memory.content.isNotBlank() &&
                        (!assistant.enableShortMemory || memory.conversationId.isNotBlank()),
                ) {
                    Text(stringResource(R.string.assistant_page_save))
                }
            },
            dismissButton = {
                TextButton(
                    onClick = {
                        memoryDialogState.dismiss()
                    }
                ) {
                    Text(stringResource(R.string.assistant_page_cancel))
                }
            }
        )
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp)
            .padding(innerPadding)
            .imePadding(),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        CardGroup {
            item(
                headlineContent = { Text(stringResource(R.string.assistant_page_memory)) },
                supportingContent = {
                    Text(
                        text = stringResource(R.string.assistant_page_memory_desc),
                    )
                },
                trailingContent = {
                    Switch(
                        checked = assistant.enableMemory,
                        onCheckedChange = {
                            onUpdateAssistant(
                                assistant.copy(
                                    // rhShortMemUI: 长期/短期互斥
                                    enableMemory = it,
                                    enableShortMemory = if (it) false else assistant.enableShortMemory
                                )
                            )
                        }
                    )
                }
            )
            // rhShortMemUI: 短期记忆(会话私有), 与长期记忆互斥
            item(
                headlineContent = { Text(stringResource(R.string.assistant_page_short_memory)) },
                supportingContent = {
                    Text(
                        text = stringResource(R.string.assistant_page_short_memory_desc),
                    )
                },
                trailingContent = {
                    Switch(
                        checked = assistant.enableShortMemory,
                        onCheckedChange = {
                            onUpdateAssistant(
                                assistant.copy(
                                    enableShortMemory = it,
                                    enableMemory = if (it) false else assistant.enableMemory,
                                    useGlobalMemory = if (it) false else assistant.useGlobalMemory
                                )
                            )
                        }
                    )
                }
            )
            item(
                headlineContent = { Text(stringResource(R.string.assistant_page_global_memory)) },
                supportingContent = {
                    Text(
                        text = stringResource(R.string.assistant_page_global_memory_desc),
                    )
                },
                trailingContent = {
                    Switch(
                        checked = assistant.useGlobalMemory,
                        onCheckedChange = {
                            onUpdateAssistant(
                                assistant.copy(
                                    useGlobalMemory = it
                                )
                            )
                        },
                        enabled = assistant.enableMemory
                    )
                }
            )
            item(
                headlineContent = { Text(stringResource(R.string.assistant_page_recent_chats)) },
                supportingContent = {
                    Text(
                        text = stringResource(R.string.assistant_page_recent_chats_desc),
                    )
                },
                trailingContent = {
                    Switch(
                        checked = assistant.enableRecentChatsReference,
                        onCheckedChange = {
                            onUpdateAssistant(
                                assistant.copy(
                                    enableRecentChatsReference = it
                                )
                            )
                        }
                    )
                }
            )
            item(
                headlineContent = { Text(stringResource(R.string.assistant_page_time_reminder)) },
                supportingContent = {
                    Text(
                        text = stringResource(R.string.assistant_page_time_reminder_desc),
                    )
                },
                trailingContent = {
                    Switch(
                        checked = assistant.enableTimeReminder,
                        onCheckedChange = {
                            onUpdateAssistant(
                                assistant.copy(
                                    enableTimeReminder = it
                                )
                            )
                        }
                    )
                }
            )
        }

        // rhMemPolish240: 工具调用介绍卡片 —— 严格只显示当前使用中的那一种模式(未开启任何记忆时不显示)
        if (assistant.enableShortMemory || assistant.enableMemory) {
            val isShort = assistant.enableShortMemory
            ActiveMemoryToolIntroCard(
                isShortTerm = isShort,
                useGlobal = assistant.useGlobalMemory && !isShort,
            )
        }

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 2.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(
                    text = stringResource(R.string.assistant_page_manage_memory_title),
                    style = MaterialTheme.typography.titleMedium,
                )
                Surface(
                    shape = RoundedCornerShape(999.dp),
                    color = MaterialTheme.colorScheme.primaryContainer,
                ) {
                    Text(
                        text = "${memories.size} 条",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onPrimaryContainer,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                    )
                }
            }

            val defaultConvId = conversationTitles.keys.firstOrNull().orEmpty()
            val canAdd = !assistant.enableShortMemory || defaultConvId.isNotBlank()
            if (canAdd) {
                IconButton(
                    onClick = {
                        memoryDialogState.open(
                            AssistantMemory(
                                id = 0,
                                content = "",
                                conversationId = if (assistant.enableShortMemory) defaultConvId else "",
                            )
                        )
                    },
                ) {
                    Icon(
                        imageVector = HugeIcons.Add01,
                        contentDescription = null
                    )
                }
            }
        }

        if (assistant.enableShortMemory) {
            // rhShortMemUI + rhMemPolish240: 短期记忆按会话分组卡片化展示
            val groupedShortMemories = memories.groupBy { it.conversationId }
            if (groupedShortMemories.isEmpty()) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CustomColors.cardColorsOnSurfaceContainer,
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(20.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        Icon(
                            imageVector = HugeIcons.Message02,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(24.dp),
                        )
                        Text(
                            text = stringResource(R.string.assistant_page_short_memory_empty),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
            groupedShortMemories.forEach { (convId, convMemories) ->
                val isCollapsed = collapsedGroups[convId] == true
                val convTitle = conversationTitles[convId]?.takeIf { it.isNotBlank() }
                    ?: stringResource(R.string.assistant_page_memory_unknown_conversation)
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp),
                    colors = CustomColors.cardColorsOnSurfaceContainer,
                ) {
                    Column(modifier = Modifier.fillMaxWidth()) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable { collapsedGroups[convId] = !isCollapsed }
                                .padding(horizontal = 14.dp, vertical = 10.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            Icon(
                                imageVector = HugeIcons.Message02,
                                contentDescription = null,
                                modifier = Modifier.size(16.dp),
                                tint = MaterialTheme.colorScheme.primary,
                            )
                            Text(
                                text = convTitle,
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.Medium,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                                modifier = Modifier.weight(1f),
                            )
                            Surface(
                                shape = RoundedCornerShape(999.dp),
                                color = MaterialTheme.colorScheme.secondaryContainer,
                            ) {
                                Text(
                                    text = "${convMemories.size} 条",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSecondaryContainer,
                                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                                )
                            }
                            IconButton(
                                onClick = {
                                    memoryDialogState.open(AssistantMemory(0, "", convId))
                                },
                                modifier = Modifier.size(32.dp),
                            ) {
                                Icon(
                                    imageVector = HugeIcons.Add01,
                                    contentDescription = null,
                                    modifier = Modifier.size(18.dp),
                                )
                            }
                            Icon(
                                imageVector = if (isCollapsed) HugeIcons.ArrowDown01 else HugeIcons.ArrowUp01,
                                contentDescription = null,
                                modifier = Modifier.size(16.dp),
                                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        AnimatedVisibility(visible = !isCollapsed) {
                            Column(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(start = 12.dp, end = 12.dp, bottom = 12.dp),
                                verticalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.4f))
                                convMemories.fastForEach { memory ->
                                    key(memory.id) {
                                        MemoryItem(
                                            memory = memory,
                                            onEditMemory = {
                                                memoryDialogState.open(it)
                                            },
                                            onDeleteMemory = {
                                                pendingDeleteMemory = it
                                            }
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }
        } else {
            if (memories.isEmpty()) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CustomColors.cardColorsOnSurfaceContainer,
                ) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(20.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(
                            text = "暂无长期记忆",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
            memories.fastForEach { memory ->
                key(memory.id) {
                    MemoryItem(
                        memory = memory,
                        onEditMemory = {
                            memoryDialogState.open(it)
                        },
                        onDeleteMemory = {
                            pendingDeleteMemory = it
                        }
                    )
                }
            }
        }
    }

    RikkaConfirmDialog(
        show = pendingDeleteMemory != null,
        title = stringResource(R.string.confirm_delete),
        confirmText = stringResource(R.string.confirm),
        dismissText = stringResource(R.string.cancel),
        onConfirm = {
            pendingDeleteMemory?.let(onDeleteMemory)
            pendingDeleteMemory = null
        },
        onDismiss = { pendingDeleteMemory = null },
        text = {
            Text(
                text = pendingDeleteMemory?.content.orEmpty(),
                maxLines = 8,
                overflow = TextOverflow.Ellipsis
            )
        }
    )
}

/**
 * rhMemPolish240: 当前启用记忆模式的工具调用介绍卡 —— 只显示正在使用的那一种模式
 */
@Composable
private fun ActiveMemoryToolIntroCard(
    isShortTerm: Boolean,
    useGlobal: Boolean,
) {
    val containerColor = if (isShortTerm) {
        MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.55f)
    } else {
        MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.55f)
    }
    val accentColor = if (isShortTerm) {
        MaterialTheme.colorScheme.secondary
    } else {
        MaterialTheme.colorScheme.primary
    }
    val modeTitle = when {
        isShortTerm -> "短期记忆工具（memory_tool · 会话私有）"
        useGlobal -> "长期记忆工具（memory_tool · 全局共享）"
        else -> "长期记忆工具（memory_tool · 助手级公共）"
    }
    val modeDesc = if (isShortTerm) {
        "调用介绍：AI 仅在当前对话内通过 memory_tool(create / edit / delete) 记录临时上下文与会话设定；记忆与具体会话绑定，其他对话无法访问。"
    } else {
        "调用介绍：AI 通过 memory_tool(create / edit / delete) 记录跨对话的长期偏好与重要事实；该助手下的所有会话均可共享访问这些记忆。"
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = containerColor),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Icon(
                    imageVector = HugeIcons.QuillWrite01,
                    contentDescription = null,
                    modifier = Modifier.size(16.dp),
                    tint = accentColor,
                )
                Text(
                    text = modeTitle,
                    style = MaterialTheme.typography.labelLarge,
                    color = accentColor,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f),
                )
                Surface(
                    shape = RoundedCornerShape(999.dp),
                    color = accentColor.copy(alpha = 0.15f),
                ) {
                    Text(
                        text = "使用中",
                        style = MaterialTheme.typography.labelSmall,
                        color = accentColor,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                    )
                }
            }
            Text(
                text = modeDesc,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun MemoryItem(
    memory: AssistantMemory,
    onEditMemory: (AssistantMemory) -> Unit,
    onDeleteMemory: (AssistantMemory) -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainerLow
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(4.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                Text(
                    text = memory.content,
                    maxLines = 5,
                    overflow = TextOverflow.Ellipsis,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            IconButton(
                onClick = { onEditMemory(memory) },
                modifier = Modifier.size(36.dp),
            ) {
                Icon(HugeIcons.PencilEdit01, null, modifier = Modifier.size(18.dp))
            }
            IconButton(
                onClick = { onDeleteMemory(memory) },
                modifier = Modifier.size(36.dp),
            ) {
                Icon(
                    HugeIcons.Delete01,
                    stringResource(R.string.assistant_page_delete),
                    modifier = Modifier.size(18.dp),
                )
            }
        }
    }
}
'''


def patch_tools():
    p = ROOT / TOOLS
    if not p.exists():
        fail('MemoryTools.kt missing')
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        print('batch240: MemoryTools already applied')
        return
    p.write_text(TOOLS_CODE, encoding='utf-8')
    if balance(TOOLS_CODE) != 0:
        fail('MemoryTools: balance != 0')
    print('batch240: MemoryTools OK')


def patch_builtin_ui():
    p = ROOT / BUILTIN_UI
    if not p.exists():
        fail('BuiltinToolUIs.kt missing')
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        print('batch240: BuiltinToolUIs already applied')
        return
    bal0 = balance(t)
    old = ('    @Composable' + NL
           + '    override fun title(context: ToolUIContext): String = when (action(context)) {' + NL
           + '        ACTION_CREATE -> stringResource(R.string.chat_message_tool_create_memory)' + NL
           + '        ACTION_EDIT -> stringResource(R.string.chat_message_tool_edit_memory)' + NL
           + '        ACTION_DELETE -> stringResource(R.string.chat_message_tool_delete_memory)' + NL
           + '        else -> stringResource(R.string.chat_message_tool_call_generic, toolName)' + NL
           + '    }')
    new = ('    // ' + MARK + ': 聊天工具调用卡片标题区分「短期记忆」与「长期记忆」' + NL
           + '    private fun isShortTerm(context: ToolUIContext): Boolean =' + NL
           + '        !context.content.getStringContent(' + Q + 'conversationId' + Q + ').isNullOrBlank() ||' + NL
           + '            context.content.getStringContent(' + Q + 'scope' + Q + ') == ' + Q + 'short' + Q + NL
           + NL
           + '    @Composable' + NL
           + '    override fun title(context: ToolUIContext): String {' + NL
           + '        val short = isShortTerm(context)' + NL
           + '        return when (action(context)) {' + NL
           + '            ACTION_CREATE -> if (short) ' + Q + '写入短期记忆' + Q + ' else ' + Q + '写入长期记忆' + Q + NL
           + '            ACTION_EDIT -> if (short) ' + Q + '更新短期记忆' + Q + ' else ' + Q + '更新长期记忆' + Q + NL
           + '            ACTION_DELETE -> if (short) ' + Q + '删除短期记忆' + Q + ' else ' + Q + '删除长期记忆' + Q + NL
           + '            else -> stringResource(R.string.chat_message_tool_call_generic, toolName)' + NL
           + '        }' + NL
           + '    }')
    t = replace_once(t, old, new, 'BuiltinToolUIs MemoryToolUI title')
    if balance(t) != bal0:
        fail('BuiltinToolUIs: balance changed')
    p.write_text(t, encoding='utf-8')
    print('batch240: BuiltinToolUIs OK')


def patch_page():
    p = ROOT / PAGE
    if not p.exists():
        fail('AssistantMemoryPage.kt missing')
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        print('batch240: AssistantMemoryPage already applied')
        return
    p.write_text(PAGE_CODE, encoding='utf-8')
    if balance(PAGE_CODE) != 0:
        fail('AssistantMemoryPage: balance != 0')
    print('batch240: AssistantMemoryPage OK')


def main():
    patch_tools()
    patch_builtin_ui()
    patch_page()
    print('::notice::batch240 OK - Memory UI & tool description polish (active-only intro card + session cards + tool title scope)')


main()
