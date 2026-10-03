#!/usr/bin/env python3
'''batch46 v5: 修 #143/#144（v4 的两个认知错误）：

错误认知1: patch 只在 runner 工作区生效、不回写仓库——每次 CI 都 fresh checkout
重新应用全部脚本。v4 以为 v2 的鲸鱼块已在仓库文件里，实际仓库里的 About 页
从来就是原始 AsyncImage。v5 直接从原始 AsyncImage 块替换（锚点=fresh checkout
恒定形态），一步到位换成 WhaleGirlMascot。

错误认知2: batch41 的 A6 是"替换"不是"插入"——v4 把收敛块删成空串，
while 循环失去 sourceGroups 更新 -> 运行时死循环（8分钟总超时兜底）。
v5 把 A6_V2 块替换回官方原版六行（partitionSources 赋值 + reductionPasses++
+ check 12 轮上限）。

WhaleGirlMascot 签名（真实读取 WhaleGirlMascot.kt）：
  WhaleGirlMascot(state: MiffanMascotState, modifier, reducedMotion,
    presentation: MiffanPresentation = Scene, interactive, attentionTarget,
    attentionId, inputState, submitId, dayPhase, generationPhase)
MiffanMascotState.Idle 存在（WhaleMascotEnums.kt）。
'''
from pathlib import Path
import re

ROOT = Path.cwd()
CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'
ABOUT = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingAboutPage.kt'

def fail(path, msg):
    print('::error file=' + path + '::batch46v5 ' + str(msg)[:1500])
    raise SystemExit(1)

# ============================================================
# 1. ChatService: 回滚 batch41 六处 -> 官方原版
# ============================================================
t = (ROOT / CS).read_text(encoding='utf-8')

if 'rhCompressFix' in t or 'rhCompressAB' in t or 'compressionJobs' in t:
    # 1a. 嵌套 async 重试块 -> 官方 4 行
    NESTED_PAT = (
        '                        async(Dispatchers.IO) {\n'
        '                            // rhCompressAB(B)'
    )
    if NESTED_PAT in t:
        i = t.find(NESTED_PAT)
        tail = '                    }.awaitAll().filterNotNull()\n'
        j = t.find(tail, i)
        if j < 0:
            fail(CS, 'nested block tail not found')
        OFFICIAL_ASYNC = (
            '                        async(Dispatchers.IO) {\n'
            '                            compressSources(group, requestedTargetTokens)\n'
            '                        }\n'
            '                    }.awaitAll()\n'
        )
        t = t[:i] + OFFICIAL_ASYNC + t[j + len(tail):]

    # 1b. 删空 summaries 检查
    t = t.replace(
        '            if (summaries.isEmpty()) {\n'
        '                throw IllegalStateException("Failed to generate compressed summary (all groups failed)")\n'
        '            }\n',
        '', 1)

    # 1c. 强制收敛块 -> 官方原版六行（v4 错删成空导致死循环）
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
    A6_OFFICIAL = (
        '            sourceGroups = ContextCompactionPlanner.partitionSources(\n'
        '                sources = summaries,\n'
        '                maxInputTokens = mapInputBudgetTokens,\n'
        '            )\n'
        '            reductionPasses++\n'
        '            check(reductionPasses <= 12) {\n'
        '                "Compression model did not reduce the conversation enough to merge its summaries"\n'
        '            }\n'
    )
    if A6_V2 in t:
        t = t.replace(A6_V2, A6_OFFICIAL, 1)
    elif 'rhCompressAB(A)' in t:
        fail(CS, 'A6 convergence block shape unexpected, cannot rollback')

    # 1d. 清理 compressionJobs 三处（字段/登记/取消）
    t = re.sub(
        r'\n    // rhCompressFix: 手动压缩跑在 appScope.*?\n    private val compressionJobs = ConcurrentHashMap<Uuid, Job>\(\)\n',
        '\n', t, count=1, flags=re.S)
    t = re.sub(
        r'\n        // rhCompressFix: 登记本会话进行中的压缩 job.*?\n        \}\n',
        '\n', t, count=1, flags=re.S)
    t = re.sub(
        r'\n        // rhCompressFix: 用户主动停止.*?\n        compressionJobs\[conversationId\]\?\.let \{ runCatching \{ it\.cancelAndJoin\(\) \} \}\n',
        '\n', t, count=1, flags=re.S)

    # 1e. 修复 v4 可能造成的损伤：若 sourceGroups 赋值丢失（v4 删空），补回
    if 'reductionPasses++' not in t:
        fail(CS, 'reductionPasses++ missing after rollback (dead loop risk)')

    for token in ['rhCompressFix', 'rhCompressAB', 'compressionJobs', 'all groups failed']:
        if token in t:
            fail(CS, 'rollback incomplete, still has: ' + token)

    (ROOT / CS).write_text(t, encoding='utf-8')
    print('batch46v5: ChatService rollback complete')
else:
    print('batch46v5: ChatService clean, skip')

# ============================================================
# 2. About: 原始 AsyncImage -> WhaleGirlMascot（fresh checkout 恒定锚点）
# ============================================================
a = (ROOT / ABOUT).read_text(encoding='utf-8')

if 'rhWhaleAbout' in a:
    print('batch46v5: about page already whale')
else:
    # 2a. import：WhaleGirlMascot + MiffanMascotState + Box（Box 原文件已有则跳过）
    UI = 'me.rerere.rikkahub.ui.components.ui.'
    anchor = 'import me.rerere.rikkahub.ui.theme.CustomColors\n'
    if anchor not in a:
        fail(ABOUT, 'CustomColors import anchor not found')
    for imp in [UI + 'WhaleGirlMascot\n', UI + 'MiffanMascotState\n']:
        if imp not in a:
            i = a.find(anchor)
            a = a[:i] + imp + a[i:]

    # 2b. 原始 AsyncImage 块 -> Box + WhaleGirlMascot
    OLD = (
        '                        AsyncImage(\n'
        '                            model = R.mipmap.ic_launcher,\n'
        '                            contentDescription = stringResource(R.string.accessibility_app_logo),\n'
        '                            modifier = Modifier\n'
        '                                .clip(CircleShape)\n'
        '                                .size(150.dp)\n'
        '                                .onGloballyPositioned { coordinates ->\n'
        '                                    val position = coordinates.positionInParent()\n'
        '                                    val size = coordinates.size\n'
        '                                    logoCenterPx = Offset(\n'
        '                                        position.x + size.width / 2f,\n'
        '                                        position.y + size.height / 2f\n'
        '                                    )\n'
        '                                }\n'
        '                                .clickable {\n'
        '                                    onBurst(logoCenterPx)\n'
        '                                }\n'
        '                        )'
    )
    NEW = (
        '                        // rhWhaleAbout: 关于页用大肥鱼替代 launcher 图标（保留点击彩蛋）\n'
        '                        Box(\n'
        '                            contentAlignment = Alignment.Center,\n'
        '                            modifier = Modifier\n'
        '                                .size(150.dp)\n'
        '                                .onGloballyPositioned { coordinates ->\n'
        '                                    val position = coordinates.positionInParent()\n'
        '                                    val size = coordinates.size\n'
        '                                    logoCenterPx = Offset(\n'
        '                                        position.x + size.width / 2f,\n'
        '                                        position.y + size.height / 2f\n'
        '                                    )\n'
        '                                }\n'
        '                                .clickable {\n'
        '                                    onBurst(logoCenterPx)\n'
        '                                }\n'
        '                        ) {\n'
        '                            WhaleGirlMascot(\n'
        '                                state = MiffanMascotState.Idle,\n'
        '                                interactive = false,\n'
        '                                modifier = Modifier.fillMaxSize(),\n'
        '                            )\n'
        '                        }'
    )
    if OLD not in a:
        fail(ABOUT, 'original AsyncImage block anchor not found')
    a = a.replace(OLD, NEW, 1)

    # 2c. Box import（原文件没有 Box）
    if 'import androidx.compose.foundation.layout.Box' not in a:
        B_ANCHOR = 'import androidx.compose.foundation.layout.Column\n'
        if B_ANCHOR not in a:
            fail(ABOUT, 'Column import anchor not found')
        i = a.find(B_ANCHOR)
        a = a[:i] + 'import androidx.compose.foundation.layout.Box\n' + a[i:]

    # 2d. fillMaxSize 已在原 import（fillMaxSize 用于 LazyColumn modifier）——校验
    if 'import androidx.compose.foundation.layout.fillMaxSize' not in a:
        fail(ABOUT, 'fillMaxSize import missing (expected in original)')

    (ROOT / ABOUT).write_text(a, encoding='utf-8')
    print('batch46v5: about page whale applied')

# 最终自检
a2 = (ROOT / ABOUT).read_text(encoding='utf-8')
for need in ['rhWhaleAbout', 'WhaleGirlMascot(', 'MiffanMascotState.Idle']:
    if need not in a2:
        fail(ABOUT, 'final selfcheck missing: ' + need)
if 'WhaleGirlPortrait' in a2:
    fail(ABOUT, 'final selfcheck: WhaleGirlPortrait must be gone')

print('batch46v5: OK')
