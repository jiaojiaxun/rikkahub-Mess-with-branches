#!/usr/bin/env python3
# rhRemote355l: @补全的 SSH 限流（P1）
# 问题: loadEntries 硬编码 MAX_INDEXED_DIRS=80 / CACHE_TTL=5s。SSH 下 80 个目录=80 次 SFTP
#       往返（100ms/次≈8s），远超 5s TTL → 缓存必然失效, 每次 @ 全量重扫。
# 方案(最优): 不改构造器(避免找 ChatPage/ChatVM 调用点), 在 loadEntries 内部用
#       repository.getById(workspaceId)?.isSsh() 自判; 远程用 20 目录/200 条目/60s TTL。
# 单文件自包含, 只多一次本地 DB 查询(微秒级)。
import os

DIAG = "ci_diag_batch355l_completion.txt"
ROOT = os.environ.get("GITHUB_WORKSPACE", os.getcwd())

path = "app/src/main/java/me/rerere/rikkahub/ui/components/ai/completion/WorkspaceCompletionProvider.kt"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

diag = []
ok = True


def patch(label, needle, repl):
    global text, ok
    if repl in text:
        diag.append(label + ":already")
        return
    if text.count(needle) != 1:
        diag.append(label + ":ANCHOR-MISMATCH(" + str(text.count(needle)) + ")")
        ok = False
        return
    text = text.replace(needle, repl, 1)
    diag.append(label + ":ok")


# 1) remote 判断 + TTL
patch(
    "ttl",
    "        val now = System.currentTimeMillis()\n"
    "        if (cachedAt > 0L && now - cachedAt < CACHE_TTL_MILLIS) {\n"
    "            return cachedEntries\n"
    "        }\n",
    "        val now = System.currentTimeMillis()\n"
    "        // 远程工作区每列一个目录都是一次 SFTP 往返: 收窄索引范围并延长缓存,\n"
    "        // 否则 80 个目录 x 100ms 远超原 5 秒 TTL, 每次 @ 都会全量重扫。\n"
    "        val remote = repository.getById(workspaceId ?: return emptyList())?.isSsh() == true\n"
    "        val ttl = if (remote) REMOTE_CACHE_TTL_MILLIS else CACHE_TTL_MILLIS\n"
    "        if (cachedAt > 0L && now - cachedAt < ttl) {\n"
    "            return cachedEntries\n"
    "        }\n",
)

# 2) 局部上限 + while 条件
patch(
    "limits",
    "        var visitedDirs = 0\n"
    "\n"
    "        while (queue.isNotEmpty() && result.size < MAX_INDEXED_ENTRIES && visitedDirs < MAX_INDEXED_DIRS) {\n",
    "        var visitedDirs = 0\n"
    "        val maxEntries = if (remote) MAX_REMOTE_INDEXED_ENTRIES else MAX_INDEXED_ENTRIES\n"
    "        val maxDirs = if (remote) MAX_REMOTE_INDEXED_DIRS else MAX_INDEXED_DIRS\n"
    "\n"
    "        while (queue.isNotEmpty() && result.size < maxEntries && visitedDirs < maxDirs) {\n",
)

# 3) 循环内条目上限
patch(
    "entries-cap",
    "                if (result.size >= MAX_INDEXED_ENTRIES) return@forEach\n",
    "                if (result.size >= maxEntries) return@forEach\n",
)

# 4) 目录入队上限
patch(
    "dirs-cap",
    "                if (entry.isDirectory && queue.size < MAX_INDEXED_DIRS && seenDirs.add(entry.path)) {\n",
    "                if (entry.isDirectory && queue.size < maxDirs && seenDirs.add(entry.path)) {\n",
)

# 5) 常量
patch(
    "consts",
    "        private const val CACHE_TTL_MILLIS = 5_000L\n",
    "        private const val CACHE_TTL_MILLIS = 5_000L\n"
    "        private const val MAX_REMOTE_INDEXED_ENTRIES = 200\n"
    "        private const val MAX_REMOTE_INDEXED_DIRS = 20\n"
    "        private const val REMOTE_CACHE_TTL_MILLIS = 60_000L\n",
)

with open(path, "w", encoding="utf-8") as f:
    f.write(text)

# 自检（只断言本批产物 + 内部一致性）
for needle in (
    "val remote = repository.getById(workspaceId ?: return emptyList())?.isSsh() == true",
    "val ttl = if (remote) REMOTE_CACHE_TTL_MILLIS else CACHE_TTL_MILLIS",
    "val maxEntries = if (remote) MAX_REMOTE_INDEXED_ENTRIES else MAX_INDEXED_ENTRIES",
    "val maxDirs = if (remote) MAX_REMOTE_INDEXED_DIRS else MAX_INDEXED_DIRS",
    "while (queue.isNotEmpty() && result.size < maxEntries && visitedDirs < maxDirs)",
    "if (result.size >= maxEntries) return@forEach",
    "if (entry.isDirectory && queue.size < maxDirs && seenDirs.add(entry.path))",
    "private const val MAX_REMOTE_INDEXED_ENTRIES = 200",
    "private const val MAX_REMOTE_INDEXED_DIRS = 20",
    "private const val REMOTE_CACHE_TTL_MILLIS = 60_000L",
):
    if needle not in text:
        diag.append("MISS:" + needle[:46])
        ok = False

# LEFTOVER: 硬编码上限不得残留于循环条件（常量定义本身要保留）
if "result.size < MAX_INDEXED_ENTRIES" in text:
    diag.append("LEFTOVER:while-hardcoded")
    ok = False
if "queue.size < MAX_INDEXED_DIRS" in text:
    diag.append("LEFTOVER:dirs-hardcoded")
    ok = False
if "now - cachedAt < CACHE_TTL_MILLIS" in text:
    diag.append("LEFTOVER:ttl-hardcoded")
    ok = False

# 括号配平（本批净差应为 0）
if text.count("{") != text.count("}"):
    diag.append("BRACES(" + str(text.count("{")) + "/" + str(text.count("}")) + ")")
    ok = False
if text.count("(") != text.count(")"):
    diag.append("PARENS(" + str(text.count("(")) + "/" + str(text.count(")")) + ")")
    ok = False

diag.append("RESULT:" + ("OK" if ok else "FAIL"))
with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
    f.write("\n".join(diag) + "\n")
print(" | ".join(diag))
if not ok:
    print("::error title=batch355l::" + " | ".join(diag))
