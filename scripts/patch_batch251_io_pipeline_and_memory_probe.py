#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch251: T-P1 生成管线挪出主线程 + T-M4 记忆不显示根因取证（Migration_36_37 + 记忆页数据源）

【T-P1 依据（已实读）】
RikkaHubApp.kt 末尾:
    class AppScope : CoroutineScope by CoroutineScope(
        SupervisorJob() + Dispatchers.Main + CoroutineName("AppScope") + CoroutineExceptionHandler{...})
ChatService.sendMessage:
    val releaseForegroundWork = foregroundWorkTracker.acquire()
    val job = appScope.launch { ... handleMessageComplete(conversationId) ... }
=> 无 dispatcher => 继承 Main。每个 suspend 恢复点都回主线程：chunk 解析、StreamChunkHandler 合并、
   session.state 更新、UIMessage.copy 全在 Main 上做，长上下文时是 O(全文)。
本批把它改成 appScope.launch(Dispatchers.IO)：
  · StateFlow 写入任意线程安全，Compose 自己在 Main 读
  · 网络/DB 的 suspend 调用本来就在自己的 dispatcher 上，不受影响
  · 不动 BrowserTools 的 Main 跳转（WebView 必须主线程）
  · 不动 AppScope 本体（RikkaHubApp 里大量 launch 依赖主线程语义：通知、WebView、启动引导）

【T-P2 说明（本批不做，故意）】
审计建议给 chunk flow 加 .conflate() —— **会丢字**：StreamChunkHandler 是有状态增量合并器，
被丢掉的 chunk 就是永久缺失的正文。正确做法是「累积照收 + 状态推送侧节流」。
但节流点必须落在 GenerationHandler 的 collect 处，本批还没读到那段，所以不动，先取证。

【T-M4 取证：根因高度可疑在 Migration_36_37 的 ALTER 语句】
已确认（batch250 的 ci_diag）:
    MemoryDAO L13/16: WHERE assistant_id = :assistantId AND conversation_id = ''
    MemoryDAO L20/23: WHERE assistant_id = :assistantId AND conversation_id = :conversationId
    MemoryRepository.getGlobalMemories() -> getMemoriesOfAssistant(GLOBAL_MEMORY_ID)
若 Migration_36_37 写的是 `ADD COLUMN conversation_id TEXT`（没有 NOT NULL DEFAULT ''），
旧备份恢复后该列是 **NULL**，而查询条件是 `= ''` => NULL 与 '' 不匹配 => 一条都不显示。
这正是「旧备份导入后记忆全部消失」的形状。
本批 dump：
  · Migration_36_37 全文件（找 ALTER 语句原文）
  · AssistantMemoryPage 里 memories 的数据源（是 getMemoriesOfAssistantFlow 还是 session 流）
  · WebDavSync 恢复 db 的路径（替换文件 vs 逐表 insert）
下一批按 ALTER 原文定修法（改查询兼容 NULL / 改迁移写 DEFAULT '' / 恢复后做一次 UPPER 修复）。

五查:
 1. import 清单: ChatService 已 import kotlinx.coroutines.Dispatchers（lifecycleObserver 里用过
    appScope.launch(Dispatchers.IO)）；本批零新增 import
 2. 同文件冲突: ChatService.kt 被 batch95/232/233/234/235/238 等改过；本批锚点为
    「foregroundWorkTracker.acquire() 紧跟 val job = appScope.launch {」两行窗口，snapshot 实读确认唯一
 3. 作用域: 只改 launch 的 dispatcher 参数，块内代码一行不动
 4. 括号配对: 仅插入 `(Dispatchers.IO)`，括号 1 对 1 => balance 不变，脚本断言
 5. 函数签名: 零改动
Python 三查: Q/SQ 变量构造引号; NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 失败记录并继续
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
DIAG = 'ci_diag_batch251.txt'

CHATSERVICE = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'
MEM_PAGE = 'app/src/main/java/me/rerere/rikkahub/ui/pages/assistant/detail/AssistantMemoryPage.kt'

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


def patch_chat_scope():
    p = ROOT / CHATSERVICE
    if not p.exists():
        note('MISSING ChatService.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhIoGen251' in t:
        note('chatScope already applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    # 两行窗口定位：acquire 行之后紧跟的 appScope.launch {
    anchor = -1
    for i, ln in enumerate(lines):
        if ln.strip() == 'val releaseForegroundWork = foregroundWorkTracker.acquire()':
            if i + 1 < len(lines) and lines[i + 1].strip() == 'val job = appScope.launch {':
                anchor = i + 1
                break
    if anchor < 0:
        note('ANCHOR-MISS sendMessage launch window')
        return

    ind = ind_of(lines[anchor])
    lines[anchor] = ind + 'val job = appScope.launch(Dispatchers.IO) { // rhIoGen251: 生成管线离开主线程'

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('chatService balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        return
    if 'val job = appScope.launch(Dispatchers.IO) { // rhIoGen251' not in t2:
        note('chatService selfcheck missing marker')
        return
    if t2.count('appScope.launch(Dispatchers.IO) {') < 1:
        note('chatService selfcheck missing dispatcher')
        return
    p.write_text(t2, encoding='utf-8')
    note('chatService OK: sendMessage pipeline -> Dispatchers.IO')


def probe_memory():
    # a) Migration_36_37 全文（关键：ALTER 语句是否带 DEFAULT ''）
    found = False
    for cand in ['app/src/main/java/me/rerere/rikkahub/data/db/Migration_36_37.kt',
                 'app/src/main/java/me/rerere/rikkahub/data/db/migrations/Migration_36_37.kt']:
        p = ROOT / cand
        if p.exists():
            found = True
            lines = p.read_text(encoding='utf-8').split(NL)
            note('migration file=' + cand + ' lines=' + str(len(lines)))
            for i, ln in enumerate(lines):
                s = ln.strip()
                if s:
                    note('mig L' + str(i + 1) + ':' + s[:200])
            break
    if not found:
        note('migration file not found in the two known paths')
        # 兜底：在 data 目录里按文件名搜
        base = ROOT / 'app/src/main/java/me/rerere/rikkahub/data'
        if base.exists():
            for path in base.rglob('Migration_36_37*.kt'):
                note('found alt migration path=' + str(path.relative_to(ROOT)))
                lines = path.read_text(encoding='utf-8').split(NL)
                for i, ln in enumerate(lines):
                    s = ln.strip()
                    if s:
                        note('mig L' + str(i + 1) + ':' + s[:200])

    # b) 记忆页 memories 的数据源
    p = ROOT / MEM_PAGE
    if not p.exists():
        note('probe missing AssistantMemoryPage.kt')
    else:
        lines = p.read_text(encoding='utf-8').split(NL)
        keys = ['memories', 'collectAsState', 'getMemoriesOfAssistant', 'getGlobalMemories',
                'getSessionMemories', 'enableShortMemory', 'useGlobalMemory']
        hits = []
        for i, ln in enumerate(lines):
            s = ln.strip()
            for k in keys:
                if k in s:
                    hits.append('L' + str(i + 1) + ':' + s[:170])
                    break
        note('probe AssistantMemoryPage data-source hits=' + str(len(hits)))
        for h in hits[:40]:
            note('page ' + h)

    # c) 恢复路径：替换 db 文件 还是逐表 insert
    p = ROOT / 'app/src/main/java/me/rerere/rikkahub/data/sync/webdav/WebDavSync.kt'
    if not p.exists():
        note('probe missing WebDavSync.kt')
    else:
        lines = p.read_text(encoding='utf-8').split(NL)
        keys = ['restoreFromLocalFile', 'copyTo(', 'restoreDatabase', 'memoryentity',
                'MemoryEntity', 'createFullDatabaseSnapshot', 'closeAndReplace', 'replaceDatabaseFile']
        hits = []
        for i, ln in enumerate(lines):
            s = ln.strip()
            for k in keys:
                if k in s:
                    hits.append('L' + str(i + 1) + ':' + s[:170])
                    break
        note('probe WebDavSync restore hits=' + str(len(hits)))
        for h in hits[:44]:
            note('webdav ' + h)


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch251 diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch251 diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    for name, fn in [
        ('1 chat pipeline to IO', patch_chat_scope),
        ('2 memory root-cause probe', probe_memory),
    ]:
        try:
            fn()
            note(name + ' DONE')
        except Exception as e:
            note(name + ' EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
        print('::error::batch251 part: ' + name)
        sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch251 ' + str(line)[:800])
    print('::error::batch251 END lines=' + str(len(report)))


main()