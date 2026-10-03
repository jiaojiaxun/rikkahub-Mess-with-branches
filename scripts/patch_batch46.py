#!/usr/bin/env python3
'''batch46 v6 (zero-backslash): 对抗性检查后的修复（#147 验尸结论）

死因（annotations 列号逐一核对）：v4/v5 的 import 插入丢了 import 关键字，
插进去的是裸限定名行，顶层裸名字 = 语法错误。列号 1,3,4,10,11,19,20,22,23,33
与 me.rerere.rikkahub.ui.components.ui.WhaleGirlMascot 的各点分段起点 10/10 吻合。

沉默错误：A6 回滚只换到 sourceGroups = nextGroups，batch41 add6 尾部的
reductionPasses++ 与 check 残留 → 双倍自增，12 轮上限实际 6 轮（合法 Kotlin
编译不报）。v6 整块替换回官方六行。

自检升级：完整 import 语句逐条在场 + 官方 A6 块在场 + 无双增模式。
本脚本全文零反斜杠（换行用 chr(10)，多行锚点用三引号），规避转义歧义。
'''
from pathlib import Path

ROOT = Path.cwd()
CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'
ABOUT = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingAboutPage.kt'
NL = chr(10)
I12 = '            '
I16 = '                '
I20 = '                    '
I24 = '                        '
I28 = '                            '


def fail(path, msg):
    print('::error file=' + path + '::batch46v6 ' + str(msg)[:1500])
    raise SystemExit(1)


# ============================================================
# 1. ChatService: 回滚 batch41 六处 -> 官方原版
# ============================================================
t = (ROOT / CS).read_text(encoding='utf-8')

if ('rhCompressFix' in t) or ('rhCompressAB' in t) or ('compressionJobs' in t):
    # 1a. 重试块 -> 官方 4 行（定位起点 + 尾行，v5 已验证的区间替换）
    NESTED_PAT = I24 + 'async(Dispatchers.IO) {' + NL + I28 + '// rhCompressAB(B)'
    if NESTED_PAT in t:
        i = t.find(NESTED_PAT)
        tail = I20 + '}.awaitAll().filterNotNull()' + NL
        j = t.find(tail, i)
        if j < 0:
            fail(CS, 'nested block tail not found')
        OFFICIAL_ASYNC = (
            I24 + 'async(Dispatchers.IO) {' + NL +
            I28 + 'compressSources(group, requestedTargetTokens)' + NL +
            I24 + '}' + NL +
            I20 + '}.awaitAll()' + NL
        )
        t = t[:i] + OFFICIAL_ASYNC + t[j + len(tail):]

    # 1b. 删空 summaries 检查
    EMPTY_CHK = (
        I12 + 'if (summaries.isEmpty()) {' + NL +
        I16 + 'throw IllegalStateException("Failed to generate compressed summary (all groups failed)")' + NL +
        I12 + '}' + NL
    )
    t = t.replace(EMPTY_CHK, '', 1)

    # 1c. v6 修正：整块替换（含 add6 尾部的 reductionPasses++/check）
    A6_V2_FULL = (
        I12 + '// rhCompressAB(A): 组数不再收敛时直接收尾，绝不无限循环打请求' + NL +
        I12 + 'val nextGroups = ContextCompactionPlanner.partitionSources(' + NL +
        I16 + 'sources = summaries,' + NL +
        I16 + 'maxInputTokens = mapInputBudgetTokens,' + NL +
        I12 + ')' + NL +
        I12 + 'if (nextGroups.size >= sourceGroups.size) {' + NL +
        I16 + 'Log.w(' + NL +
        I20 + 'TAG,' + NL +
        I20 + '"Compaction not converging: groups=${sourceGroups.size} -> " +' + NL +
        I24 + '"${nextGroups.size}; accepting combined summary (" +' + NL +
        I24 + 'ContextCompactionPlanner.estimateTokens(combinedSummary) + " tokens)",' + NL +
        I16 + ')' + NL +
        I16 + 'finalSummary = combinedSummary' + NL +
        I16 + 'continue' + NL +
        I12 + '}' + NL +
        I12 + 'sourceGroups = nextGroups' + NL +
        I12 + 'reductionPasses++' + NL +
        I12 + 'check(reductionPasses <= 12) {' + NL +
        I16 + '"Compression model did not reduce the conversation enough to merge its summaries"' + NL +
        I12 + '}' + NL
    )
    A6_OFFICIAL = (
        I12 + 'sourceGroups = ContextCompactionPlanner.partitionSources(' + NL +
        I16 + 'sources = summaries,' + NL +
        I16 + 'maxInputTokens = mapInputBudgetTokens,' + NL +
        I12 + ')' + NL +
        I12 + 'reductionPasses++' + NL +
        I12 + 'check(reductionPasses <= 12) {' + NL +
        I16 + '"Compression model did not reduce the conversation enough to merge its summaries"' + NL +
        I12 + '}' + NL
    )
    if A6_V2_FULL in t:
        t = t.replace(A6_V2_FULL, A6_OFFICIAL, 1)
    else:
        fail(CS, 'A6 full block not found (add6 shape unexpected)')

    # 1d. compressionJobs 三处（find/切片，不用正则）
    m = t.find('// rhCompressFix: 手动压缩跑在 appScope')
    if m >= 0:
        start = t.rfind(NL, 0, m)
        k = t.find('private val compressionJobs = ConcurrentHashMap<Uuid, Job>()', m)
        if k < 0:
            fail(CS, 'compressionJobs field not found')
        end = t.find(NL, k)
        if end < 0:
            fail(CS, 'compressionJobs field end not found')
        t = t[:start] + t[end:]

    m = t.find('// rhCompressFix: 登记本会话进行中的压缩 job')
    if m >= 0:
        start = t.rfind(NL, 0, m)
        k = t.find('self.invokeOnCompletion { compressionJobs.remove(conversationId, self) }', m)
        if k < 0:
            fail(CS, 'invokeOnCompletion line not found')
        e1 = t.find(NL, k)
        e2 = t.find(NL, e1 + 1)
        if e1 < 0 or e2 < 0:
            fail(CS, 'registration block end not found')
        t = t[:start] + t[e2:]

    m = t.find('// rhCompressFix: 用户主动停止')
    if m >= 0:
        start = t.rfind(NL, 0, m)
        k = t.find('compressionJobs[conversationId]?.let { runCatching { it.cancelAndJoin() } }', m)
        if k < 0:
            fail(CS, 'cancelAndJoin line not found')
        end = t.find(NL, k)
        if end < 0:
            fail(CS, 'cancelAndJoin end not found')
        t = t[:start] + t[end:]

    # 1e. 自检：token 消失 + 官方块在场 + 无双增
    for token in ['rhCompressFix', 'rhCompressAB', 'compressionJobs', 'all groups failed']:
        if token in t:
            fail(CS, 'rollback incomplete, still has: ' + token)
    if A6_OFFICIAL not in t:
        fail(CS, 'official A6 block not restored')
    if (A6_OFFICIAL + I12 + 'reductionPasses++' + NL) in t:
        fail(CS, 'double reductionPasses++ remains')

    (ROOT / CS).write_text(t, encoding='utf-8')
    print('batch46v6: ChatService rollback complete')
else:
    print('batch46v6: ChatService clean, skip')

# ============================================================
# 2. About: 原始 AsyncImage -> WhaleGirlMascot（fresh checkout 恒定锚点）
# ============================================================
a = (ROOT / ABOUT).read_text(encoding='utf-8')

if 'rhWhaleAbout' in a:
    print('batch46v6: about page already whale')
else:
    # 2a. import（v6 修正：带 import 关键字！）
    UI = 'me.rerere.rikkahub.ui.components.ui.'
    anchor = 'import me.rerere.rikkahub.ui.theme.CustomColors' + NL
    if anchor not in a:
        fail(ABOUT, 'CustomColors import anchor not found')
    for name in ['WhaleGirlMascot', 'MiffanMascotState']:
        imp = 'import ' + UI + name + NL
        if imp not in a:
            i = a.find(anchor)
            a = a[:i] + imp + a[i:]

    # 2b. 原始 AsyncImage 块 -> Box + WhaleGirlMascot
    OLD = '''                        AsyncImage(
                            model = R.mipmap.ic_launcher,
                            contentDescription = stringResource(R.string.accessibility_app_logo),
                            modifier = Modifier
                                .clip(CircleShape)
                                .size(150.dp)
                                .onGloballyPositioned { coordinates ->
                                    val position = coordinates.positionInParent()
                                    val size = coordinates.size
                                    logoCenterPx = Offset(
                                        position.x + size.width / 2f,
                                        position.y + size.height / 2f
                                    )
                                }
                                .clickable {
                                    onBurst(logoCenterPx)
                                }
                        )'''
    NEW = '''                        // rhWhaleAbout: 关于页用大肥鱼替代 launcher 图标（保留点击彩蛋）
                        Box(
                            contentAlignment = Alignment.Center,
                            modifier = Modifier
                                .size(150.dp)
                                .onGloballyPositioned { coordinates ->
                                    val position = coordinates.positionInParent()
                                    val size = coordinates.size
                                    logoCenterPx = Offset(
                                        position.x + size.width / 2f,
                                        position.y + size.height / 2f
                                    )
                                }
                                .clickable {
                                    onBurst(logoCenterPx)
                                }
                        ) {
                            WhaleGirlMascot(
                                state = MiffanMascotState.Idle,
                                interactive = false,
                                modifier = Modifier.fillMaxSize(),
                            )
                        }'''
    if OLD not in a:
        fail(ABOUT, 'original AsyncImage block anchor not found')
    a = a.replace(OLD, NEW, 1)

    # 2c. Box import
    if 'import androidx.compose.foundation.layout.Box' + NL not in a:
        b_anchor = 'import androidx.compose.foundation.layout.Column' + NL
        if b_anchor not in a:
            fail(ABOUT, 'Column import anchor not found')
        i = a.find(b_anchor)
        a = a[:i] + 'import androidx.compose.foundation.layout.Box' + NL + a[i:]

    # 2d. fillMaxSize 依赖校验
    if 'import androidx.compose.foundation.layout.fillMaxSize' not in a:
        fail(ABOUT, 'fillMaxSize import missing (expected in original)')

    (ROOT / ABOUT).write_text(a, encoding='utf-8')
    print('batch46v6: about page whale applied')

# 最终自检（校验完整 import 语句，堵 v4/v5 的盲区）
a2 = (ROOT / ABOUT).read_text(encoding='utf-8')
for need in [
    'rhWhaleAbout',
    'WhaleGirlMascot(',
    'MiffanMascotState.Idle',
    'import me.rerere.rikkahub.ui.components.ui.WhaleGirlMascot',
    'import me.rerere.rikkahub.ui.components.ui.MiffanMascotState',
    'import androidx.compose.foundation.layout.Box',
]:
    if need not in a2:
        fail(ABOUT, 'final selfcheck missing: ' + need)
if 'WhaleGirlPortrait' in a2:
    fail(ABOUT, 'final selfcheck: WhaleGirlPortrait must be gone')

print('batch46v6: OK')
