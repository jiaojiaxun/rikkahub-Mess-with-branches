#!/usr/bin/env python3
'''batch41 v2: 修压缩「取消又请求」+「Failed to generate compressed summary」+ 无收敛死循环

根因（源码已读确认）：
  B) compressSources 空结果抛 IllegalStateException；compressGroups 用 async+awaitAll，
     一个失败 → coroutineScope 取消其余 3 个 → 整体失败。无重试。
  A) while 退出条件是「合计 <= mapInputBudgetTokens」，但重新分组用同一预算，
     组数可能永不减少 → 最多 12 轮 + 8 分钟总超时 → 必失败。
  C) compressConversationAsync 跑在 appScope，stopGeneration 不取消它 → 取消了又在请求。

v2 只改自检：v1 六个锚点全部命中，但错误地断言注释标记个数
（rhCompressFix 实际 3 处却期 4；rhCompressAB 实际 2 处却期 3）而回滚。改为存在性检查。
'''
from pathlib import Path

ROOT = Path.cwd()
P = "app/src/main/java/me/rerere/rikkahub/service/ChatService.kt"
MARK = "rhCompressFix"


def fail(anchor, msg):
    print('::error file=' + P + '::batch41 [' + anchor + '] ' + msg[:1200])
    raise SystemExit(1)


t = (ROOT / P).read_text(encoding="utf-8")
if MARK in t:
    print("batch41: already applied")
    raise SystemExit(0)

# --- 1. 声明 compressionJobs ---
A1 = '''    private val compactionMutexes = ConcurrentHashMap<Uuid, Mutex>()
'''
if A1 not in t:
    fail("A1_compactionMutexes", "anchor not found")
add1 = '''    // rhCompressFix: 手动压缩跑在 appScope（故意活过聊天页），/stop 不会取消它，
    // 表现为“取消了又在请求”。登记 job 供 stopGeneration 取消。
    private val compressionJobs = ConcurrentHashMap<Uuid, Job>()
'''
t = t.replace(A1, A1 + add1, 1)

# --- 2. compressConversationAsync 登记 job ---
A2 = '''    ): Job = appScope.launch {
        compressConversation(
'''
if A2 not in t:
    fail("A2_compressAsync", "anchor not found")
add2 = '''        // rhCompressFix: 登记本会话进行中的压缩 job，供 /stop 取消
        coroutineContext[Job]?.let { self ->
            compressionJobs[conversationId] = self
            self.invokeOnCompletion { compressionJobs.remove(conversationId, self) }
        }
'''
t = t.replace(A2, '    ): Job = appScope.launch {\n' + add2 + '        compressConversation(\n', 1)

# --- 3. stopGeneration 取消压缩 ---
A3 = '''    suspend fun stopGeneration(conversationId: Uuid) {
        val convMutex = mutexFor(conversationId)
'''
if A3 not in t:
    fail("A3_stopGeneration", "anchor not found")
add3 = '''    suspend fun stopGeneration(conversationId: Uuid) {
        // rhCompressFix: 用户主动停止 → 进行中的手动压缩也必须停，否则它继续发请求
        compressionJobs[conversationId]?.let { runCatching { it.cancelAndJoin() } }
        val convMutex = mutexFor(conversationId)
'''
t = t.replace(A3, add3, 1)

# --- 4. 单请求失败重试1次，失败不连坐 ---
A4 = '''                        async(Dispatchers.IO) {
                            compressSources(group, requestedTargetTokens)
                        }
                    }.awaitAll()
'''
if A4 not in t:
    fail("A4_compressGroups", "anchor not found")
add4 = '''                        async(Dispatchers.IO) {
                            // rhCompressAB(B): 单请求失败重试1次；仍失败则返回 null，
                            // 绝不因一个失败经 awaitAll 连坐取消并发的兄弟请求。
                            var out: String? = null
                            var lastError: Throwable? = null
                            var attempt = 0
                            while (out == null && attempt < 2) {
                                attempt++
                                try {
                                    out = compressSources(group, requestedTargetTokens)
                                } catch (c: kotlinx.coroutines.CancellationException) {
                                    throw c
                                } catch (err: Throwable) {
                                    lastError = err
                                    Log.w(TAG, "compressGroups attempt ${attempt} failed: ${err.message}")
                                }
                            }
                            if (out == null) {
                                Log.w(TAG, "compressGroups: group skipped after retry: ${lastError}")
                            }
                            out
                        }
                    }.awaitAll().filterNotNull()
'''
t = t.replace(A4, add4, 1)

# --- 5. 全部组失败时给出明确错误 ---
A5 = '''            val summaries = compressGroups(sourceGroups, passTargetTokens)
            val combinedSummary = summaries.joinToString("\\n\\n")
'''
if A5 not in t:
    fail("A5_summaries", "anchor not found")
add5 = '''            val summaries = compressGroups(sourceGroups, passTargetTokens)
            if (summaries.isEmpty()) {
                throw IllegalStateException("Failed to generate compressed summary (all groups failed)")
            }
            val combinedSummary = summaries.joinToString("\\n\\n")
'''
t = t.replace(A5, add5, 1)

# --- 6. 强制收敛 ---
A6 = '''            sourceGroups = ContextCompactionPlanner.partitionSources(
                sources = summaries,
                maxInputTokens = mapInputBudgetTokens,
            )
            reductionPasses++
            check(reductionPasses <= 12) {
                "Compression model did not reduce the conversation enough to merge its summaries"
            }
'''
if A6 not in t:
    fail("A6_convergence", "anchor not found")
add6 = '''            // rhCompressAB(A): 组数不再收敛时直接收尾，绝不无限循环打请求
            val nextGroups = ContextCompactionPlanner.partitionSources(
                sources = summaries,
                maxInputTokens = mapInputBudgetTokens,
            )
            if (nextGroups.size >= sourceGroups.size) {
                Log.w(
                    TAG,
                    "Compaction not converging: groups=${sourceGroups.size} -> " +
                        "${nextGroups.size}; accepting combined summary (" +
                        ContextCompactionPlanner.estimateTokens(combinedSummary) + " tokens)",
                )
                finalSummary = combinedSummary
                continue
            }
            sourceGroups = nextGroups
            reductionPasses++
            check(reductionPasses <= 12) {
                "Compression model did not reduce the conversation enough to merge its summaries"
            }
'''
t = t.replace(A6, add6, 1)

# --- 自检：存在性（不数注释个数，v1 就是在这里误杀）---
required = [
    "private val compressionJobs = ConcurrentHashMap<Uuid, Job>()",
    "compressionJobs[conversationId] = self",
    "compressionJobs[conversationId]?.let { runCatching { it.cancelAndJoin() } }",
    "}.awaitAll().filterNotNull()",
    "if (summaries.isEmpty()) {",
    "all groups failed",
    "if (nextGroups.size >= sourceGroups.size) {",
]
for r in required:
    if r not in t:
        fail("selfcheck_missing", repr(r))

cnt = t.count("compressionJobs")
if cnt != 4:
    fail("selfcheck_count", "compressionJobs=" + str(cnt) + " expect 4")

(ROOT / P).write_text(t, encoding="utf-8")
print("batch41 v2: OK (6 anchors applied, " + str(len(required)) + " presence checks passed)")
