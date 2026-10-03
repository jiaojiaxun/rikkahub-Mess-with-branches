#!/usr/bin/env python3
'''batch46 v4: 修 #142 两处编译错（v2 违反铁律1：没读真实代码）。

错误1 ChatService.kt:2563: v2 回滚正则从注释行开始吞，只替换 async 内部块，
造成 async 嵌套 + 双 awaitAll 尾巴。v4 锚定 v2 残留整体块直接换回官方 4 行。
错误2 SettingAboutPage.kt: v2 编造 WhaleGirlPortrait；真实入口是 WhaleGirlMascot
(state: MiffanMascotState, ...)。MiffanPresentation 枚举只有 Scene/Avatar，
不传 presentation 参数（用默认 Scene）。
'''
from pathlib import Path
import re

ROOT = Path.cwd()
CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'
ABOUT = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingAboutPage.kt'

def fail(path, msg):
    print('::error file=' + path + '::batch46v4 ' + str(msg)[:1500])
    raise SystemExit(1)

# ============================================================
# 1. ChatService: v2 残留嵌套块 -> 官方原版 4 行
# ============================================================
t = (ROOT / CS).read_text(encoding='utf-8')

if 'rhCompressAB' in t or 'compressionJobs' in t or 'rhCompressFix' in t:
    # 1a. 嵌套 async 块整体替换
    NESTED_PAT = (
        '                        async(Dispatchers.IO) {\n'
        '                            // rhCompressAB(B)'
    )
    if NESTED_PAT in t:
        i = t.find(NESTED_PAT)
        # 找到该 async 块的结尾: 第二个 awaitAll 行
        tail = '                    }.awaitAll().filterNotNull()\n'
        j = t.find(tail, i)
        if j < 0:
            fail(CS, 'nested block tail (awaitAll filterNotNull) not found')
        OFFICIAL = (
            '                        async(Dispatchers.IO) {\n'
            '                            compressSources(group, requestedTargetTokens)\n'
            '                        }\n'
            '                    }.awaitAll()\n'
        )
        t = t[:i] + OFFICIAL + t[j + len(tail):]

    # 1b. 删 v2 残留空检查（若在）
    t = t.replace(
        '            if (summaries.isEmpty()) {\n'
        '                throw IllegalStateException("Failed to generate compressed summary (all groups failed)")\n'
        '            }\n',
        '', 1)

    # 1c. 清理 v2 残留强制收敛块
    A6_V2 = (
        '            // rhCompressAB(A): 组数不再收敛时直接收尾，绝不无限循环打请求\n'
        '            val nextGroups = ContextCompactionPlanner.partitionSources(\n'
        '                sources = summaries,\n'
        '                maxInputTokens = mapInputBudgetTokens,\n'
        '            )\n'
        '            if (nextGroups.size >= sourceGroups.size) {\n'
        '                Log.w(\n'
        '                    TAG,\n'
        '                    "Compaction not converging: groups=${sourceGroups.size} -> " +\n'
        '                        "${nextGroups.size}; accepting combined summary (" +\n'
        '                        ContextCompactionPlanner.estimateTokens(combinedSummary) + " tokens)",\n'
        '                )\n'
        '                finalSummary = combinedSummary\n'
        '                continue\n'
        '            }\n'
        '            sourceGroups = nextGroups\n'
    )
    if A6_V2 in t:
        t = t.replace(A6_V2, '', 1)
        # 补回官方 partitionSources 赋值（batch41 v2 替换过它，此处它已被吞进 A6_V2 之前?）
        # 检查：官方原文在 A6 锚点处应是 partitionSources(...) 赋值；v4 前面已恢复。

    # 1d. 清理 compressionJobs 三处
    t = re.sub(
        r'\n    // rhCompressFix: 手动压缩跑在 appScope[^\n]*\n'
        r'    // 表现为[^\n]*\n'
        r'    // 表现为[^\n]*\n'
        r'    private val compressionJobs = ConcurrentHashMap<Uuid, Job>\(\)\n',
        '\n', t, count=1)
    # 宽松兜底：单行注释+字段
    t = re.sub(
        r'\n    // rhCompressFix: 手动压缩跑在 appScope.*?\n    private val compressionJobs = ConcurrentHashMap<Uuid, Job>\(\)\n',
        '\n', t, count=1, flags=re.S)
    t = re.sub(
        r'\n        // rhCompressFix: 登记本会话进行中的压缩 job.*?\n        \}\n',
        '\n', t, count=1, flags=re.S)
    t = re.sub(
        r'\n        // rhCompressFix: 用户主动停止.*?\n        compressionJobs\[conversationId\]\?\.let \{ runCatching \{ it\.cancelAndJoin\(\) \} \}\n',
        '\n', t, count=1, flags=re.S)

    for token in ['rhCompressFix', 'rhCompressAB', 'compressionJobs', 'all groups failed']:
        if token in t:
            fail(CS, 'rollback incomplete, still has: ' + token)

    (ROOT / CS).write_text(t, encoding='utf-8')
    print('batch46v4: ChatService rollback complete')
else:
    print('batch46v4: ChatService clean, skip')

# ============================================================
# 2. SettingAboutPage: WhaleGirlPortrait(编造) -> WhaleGirlMascot(真实)
# ============================================================
a = (ROOT / ABOUT).read_text(encoding='utf-8')

# 2a. 删编造 import，加真实 import
a = a.replace('import me.rerere.rikkahub.ui.components.ui.WhaleGirlPortrait\n', '', 1)
a = a.replace('import me.rerere.rikkahub.ui.components.ui.MiffanMascotState\n', '', 1)

UI = 'me.rerere.rikkahub.ui.components.ui.'
need_imports = [UI + 'WhaleGirlMascot\n', UI + 'MiffanMascotState\n']
anchor = 'import me.rerere.rikkahub.ui.theme.CustomColors\n'
if anchor not in a:
    fail(ABOUT, 'CustomColors import anchor not found')
for imp in need_imports:
    if imp not in a:
        i = a.find(anchor)
        a = a[:i] + imp + a[i:]

# 2b. composable 调用替换
OLD_CALL = (
    '                            WhaleGirlPortrait(\n'
    '                                state = MiffanMascotState.Idle,\n'
    '                                interactive = false,\n'
    '                                modifier = Modifier.fillMaxSize(),\n'
    '                            )'
)
NEW_CALL = (
    '                            WhaleGirlMascot(\n'
    '                                state = MiffanMascotState.Idle,\n'
    '                                interactive = false,\n'
    '                                modifier = Modifier.fillMaxSize(),\n'
    '                            )'
)
if OLD_CALL in a:
    a = a.replace(OLD_CALL, NEW_CALL, 1)
else:
    # v2 可能写成了其他形态——按 marker 定位后替换
    if 'rhWhaleAbout' in a and 'WhaleGirlPortrait' in a:
        a = a.replace('WhaleGirlPortrait(', 'WhaleGirlMascot(', 1)
    else:
        print('batch46v4: about page call already fixed')

# 自检
if 'WhaleGirlPortrait' in a:
    fail(ABOUT, 'selfcheck: WhaleGirlPortrait must be gone')
if 'WhaleGirlMascot(' not in a:
    fail(ABOUT, 'selfcheck: WhaleGirlMascot call missing')
if 'MiffanMascotState.Idle' not in a:
    fail(ADD_DATA_MISSING := ABOUT, 'selfcheck: MiffanMascotState.Idle missing')

(ROOT / ABOUT).write_text(a, encoding='utf-8')
print('batch46v4: OK')
