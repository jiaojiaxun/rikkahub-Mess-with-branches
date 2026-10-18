#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch238: 修复流式回复期间 O(n²) 上下文估算与派生状态重算

根因(读 snapshot 实读确认):
  1. ChatList.kt:
     - batch21c 将 estimatedContextTokens 改为 LaunchedEffect(conversation.messageNodes, loading)。
       虽然 loading=true 时函数体内 if (!loading) 跳过重算, 但把整个 conversation.messageNodes 列表
       作为 LaunchedEffect 的 key1, 导致流式期间每收到一个 token 都对全部 N 个历史节点执行
       ArrayList.equals -> MessageNode.equals -> UIMessage.equals 深度对比(O(n)/token = 全程 O(n²)),
       并且每个 token 都在主线程 cancel 旧协程 + dispatch 新协程!
     - 同文件紧邻的 subAgentPendingCount = remember(conversation.messageNodes) { ... } 同样在每个
       流式 token 上对比整表并扫描全部节点与 parts。
  2. ChatPage.kt:
     - batch228 新增的 rhPlanTodos = remember(conversation.currentMessages) { findActivePlan(...) }
       在每个流式 token 上调用 currentMessages(每次 map 分配新列表)、对比全表并重跑 findActivePlan。
  3. ContextBudgetPlanner.kt:
     - estimateMessageTokens(message: UIMessage) 无单消息缓存, 每次在轮次边界或工具步骤后调用
       estimateInputTokens / estimateContextTokens 时, 都会对所有历史消息逐字符遍历(text.forEach)。

修复方案(三层根治):
  1. ChatList.kt:
     - 移除每 token 重启的 LaunchedEffect(conversation.messageNodes, loading);
     - 改用 O(1) 流式冻结键:
       val rhEstimateKey: Any = if (loading) Triple(conversation.id, conversation.messageNodes.size, lastMessageNodeId) else conversation.messageNodes
       流式期间 key 是 3 元组(O(1) 比较, 零列表遍历, 零协程调度); 流式结束 loading 变 false 时
       key 从 Triple 切换为 List(Triple != List 必然触发重算), 立即同步算出含最新 usage 的精确值;
       空闲时增删改/切分支/切会话均直接响应。
     - subAgentPendingCount 同理: 流式期间 key 仅看 (conversation.id, messageNodes.size, 末条消息 pending 数)。
  2. ChatPage.kt:
     - rhPlanTodos 流式期间 key 仅看 Triple(conversation.id, conversation.messageNodes.size, 末条消息最新 todo_write input),
       普通文本/思考 token 流式期间 O(1) 命中, 不再分配 currentMessages; 一旦模型发出或更新 todo_write 立即响应。
  3. ContextBudgetPlanner.kt:
     - 新增线程安全有界 LRU 缓存(1024 条), 以 MessageCacheKey(message.id, System.identityHashCode(message))
       为 O(1) 键(UIMessage 为不可变 data class, id + 引用 identity 唯一标识内容且 hashCode/equals 零字符串遍历),
       历史消息估算从 O(字符数) 降为 O(1)。

五查:
1. import 清单: 零新增 import(Triple/LinkedHashMap/Collections 均为 stdlib/java.util 默认或全限定可用)
2. 同文件冲突: 锚点全部取自 snapshot 真形态(batch15/21c/55/228 应用后)
3. 作用域: ChatListNormal 内 loading/conversation/lastMessageNodeId 均在作用域;
   ChatPageContent 内 loadingJob/conversation/setting 均在作用域
4. 括号配对: 逐文件断言修改前后 balance 一致
5. 函数签名: 不改任何函数签名

Python 三查: 引号用 Q 变量构造; NL 手写 concat 禁 f-string/join/walrus; helper 先定义后用; fail-loud
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhCtxOn2Fix238'

PLANNER = 'app/src/main/java/me/rerere/rikkahub/data/ai/ContextBudgetPlanner.kt'
CHATLIST = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'
CHATPAGE = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'


def fail(msg):
    print('::error::batch238 ' + str(msg)[:1400])
    sys.stdout.flush()
    sys.exit(1)


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


def patch_planner():
    p = ROOT / PLANNER
    if not p.exists():
        fail('ContextBudgetPlanner.kt missing')
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        print('batch238: planner already applied')
        return
    bal0 = balance(t)

    old = ('    fun estimateMessageTokens(message: UIMessage): Long {' + NL
           + '        val contentTokens = message.parts.sumOf(::estimatePartTokens)' + NL
           + '        return MESSAGE_OVERHEAD_TOKENS + contentTokens' + NL
           + '    }')
    new = ('    // ' + MARK + ': 不可变 UIMessage 实例级 O(1) 估算缓存, 避免长对话每轮重复逐字符扫描历史消息' + NL
           + '    private data class MessageCacheKey(val id: Any, val identity: Int)' + NL
           + '    private const val MAX_MESSAGE_CACHE_SIZE = 1024' + NL
           + '    private val messageTokenCache: MutableMap<MessageCacheKey, Long> =' + NL
           + '        java.util.Collections.synchronizedMap(' + NL
           + '            object : java.util.LinkedHashMap<MessageCacheKey, Long>(256, 0.75f, true) {' + NL
           + '                override fun removeEldestEntry(eldest: MutableMap.MutableEntry<MessageCacheKey, Long>?): Boolean =' + NL
           + '                    size > MAX_MESSAGE_CACHE_SIZE' + NL
           + '            }' + NL
           + '        )' + NL
           + NL
           + '    fun estimateMessageTokens(message: UIMessage): Long {' + NL
           + '        val key = MessageCacheKey(message.id, System.identityHashCode(message))' + NL
           + '        messageTokenCache[key]?.let { return it }' + NL
           + '        val contentTokens = message.parts.sumOf(::estimatePartTokens)' + NL
           + '        val total = MESSAGE_OVERHEAD_TOKENS + contentTokens' + NL
           + '        messageTokenCache[key] = total' + NL
           + '        return total' + NL
           + '    }')
    t = replace_once(t, old, new, 'planner estimateMessageTokens')
    if balance(t) != bal0:
        fail('planner: balance changed')
    p.write_text(t, encoding='utf-8')
    print('batch238: ContextBudgetPlanner OK')


def patch_chatlist():
    p = ROOT / CHATLIST
    if not p.exists():
        fail('ChatList.kt missing')
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        print('batch238: chatlist already applied')
        return
    bal0 = balance(t)

    old = ('    // rhSubAgentBanner: 计算待审批工具数量' + NL
           + '    val subAgentPendingCount = remember(conversation.messageNodes) {' + NL
           + '        conversation.messageNodes.count { node ->' + NL
           + '            node.currentMessage.parts.any { part ->' + NL
           + '                part is UIMessagePart.Tool && part.approvalState is ToolApprovalState.Pending' + NL
           + '            }' + NL
           + '        }' + NL
           + '    }' + NL
           + '    val lastMessageNodeId = conversation.messageNodes.lastOrNull()?.id' + NL
           + '    // 任务12 v2：流式期间（loading=true）冻结估算，空闲时对任何消息变化' + NL
           + '    // （发送/删除/编辑/分支）都重算——v1 只认 loading 边沿是回归。' + NL
           + '    var estimatedContextTokens by remember {' + NL
           + '        mutableStateOf(ContextBudgetPlanner.estimateInputTokens(conversation.currentMessages).takeIf { it > 0 })' + NL
           + '    }' + NL
           + '    LaunchedEffect(conversation.messageNodes, loading) {' + NL
           + '        if (!loading) {' + NL
           + '            estimatedContextTokens = ContextBudgetPlanner.estimateInputTokens(' + NL
           + '                conversationUpdated.currentMessages' + NL
           + '            ).takeIf { it > 0 }' + NL
           + '        }' + NL
           + '    }')

    new = ('    val lastMessageNodeId = conversation.messageNodes.lastOrNull()?.id' + NL
           + '    // ' + MARK + ': 流式期间(loading=true)用 O(1) 三元组冻结 key, 彻底消除每 token 对' + NL
           + '    // List<MessageNode> 的 O(n) equals 遍历与 LaunchedEffect 协程频繁重启;' + NL
           + '    // 流式结束(loading->false) key 从 Triple 切回 List, 立即同步精算。' + NL
           + '    val rhLastPendingCount = conversation.messageNodes.lastOrNull()?.currentMessage?.parts?.count {' + NL
           + '        it is UIMessagePart.Tool && it.approvalState is ToolApprovalState.Pending' + NL
           + '    } ?: 0' + NL
           + '    val rhPendingKey: Any = if (loading) {' + NL
           + '        Triple(conversation.id, conversation.messageNodes.size, rhLastPendingCount)' + NL
           + '    } else {' + NL
           + '        conversation.messageNodes' + NL
           + '    }' + NL
           + '    // rhSubAgentBanner: 计算待审批工具数量' + NL
           + '    val subAgentPendingCount = remember(rhPendingKey) {' + NL
           + '        conversation.messageNodes.count { node ->' + NL
           + '            node.currentMessage.parts.any { part ->' + NL
           + '                part is UIMessagePart.Tool && part.approvalState is ToolApprovalState.Pending' + NL
           + '            }' + NL
           + '        }' + NL
           + '    }' + NL
           + '    val rhEstimateKey: Any = if (loading) {' + NL
           + '        Triple(conversation.id, conversation.messageNodes.size, lastMessageNodeId)' + NL
           + '    } else {' + NL
           + '        conversation.messageNodes' + NL
           + '    }' + NL
           + '    val estimatedContextTokens = remember(rhEstimateKey) {' + NL
           + '        ContextBudgetPlanner.estimateInputTokens(conversation.currentMessages).takeIf { it > 0 }' + NL
           + '    }')

    t = replace_once(t, old, new, 'chatlist estimate + pending')
    if balance(t) != bal0:
        fail('chatlist: balance changed')
    if 'LaunchedEffect(conversation.messageNodes, loading)' in t:
        fail('chatlist: old LaunchedEffect still present')
    p.write_text(t, encoding='utf-8')
    print('batch238: ChatList OK')


def patch_chatpage():
    p = ROOT / CHATPAGE
    if not p.exists():
        fail('ChatPage.kt missing')
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        print('batch238: chatpage already applied')
        return
    bal0 = balance(t)

    old = ('    // rhPlanBar228: 计划细条数据,取最新一次已执行的 todo_write,开关关闭时置空隐藏' + NL
           + '    val rhPlanTodos = if (setting.displaySetting.showPlanBar) {' + NL
           + '        remember(conversation.currentMessages) {' + NL
           + '            me.rerere.rikkahub.ui.components.message.findActivePlan(conversation.currentMessages)' + NL
           + '        }' + NL
           + '    } else {' + NL
           + '        emptyList()' + NL
           + '    }')

    new = ('    // rhPlanBar228 + ' + MARK + ': 流式期间仅按 (会话id, 节点数, 末条消息最新 todo_write 输入) 触发重算,' + NL
           + '    // 避免普通文本流式每 token 分配 currentMessages 与 O(n) 列表对比' + NL
           + '    val rhLastTodoInput = conversation.messageNodes.lastOrNull()?.currentMessage?.parts' + NL
           + '        ?.lastOrNull { it is UIMessagePart.Tool && it.toolName == me.rerere.rikkahub.data.ai.tools.TODO_TOOL_NAME }' + NL
           + '        ?.let { (it as UIMessagePart.Tool).input }' + NL
           + '    val rhPlanKey: Any = if (loadingJob != null) {' + NL
           + '        Triple(conversation.id, conversation.messageNodes.size, rhLastTodoInput)' + NL
           + '    } else {' + NL
           + '        conversation.messageNodes' + NL
           + '    }' + NL
           + '    val rhPlanTodos = if (setting.displaySetting.showPlanBar) {' + NL
           + '        remember(rhPlanKey) {' + NL
           + '            me.rerere.rikkahub.ui.components.message.findActivePlan(conversation.currentMessages)' + NL
           + '        }' + NL
           + '    } else {' + NL
           + '        emptyList()' + NL
           + '    }')

    t = replace_once(t, old, new, 'chatpage rhPlanTodos')
    if balance(t) != bal0:
        fail('chatpage: balance changed')
    p.write_text(t, encoding='utf-8')
    print('batch238: ChatPage OK')


def main():
    patch_planner()
    patch_chatlist()
    patch_chatpage()
    print('::notice::batch238 OK - O(n^2) streaming context estimate & derived state fixed (O(1) key + message LRU cache)')


main()
