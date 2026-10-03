#!/usr/bin/env python3
'''batch46: 用户反馈四连修（2026-10-03）

1. 压缩失败「all groups failed」→ 用户拍板回滚 batch41 的白名单方案，恢复官方原版行为。
   官方原版：单组失败直接抛 IllegalStateException（无重试、连坐取消）；
   用户说「恢复原版官方的恢复方案」，即回滚 batch41 的六处修改（保留 batch3 的流式预览，那是官方没有的独立功能，且用户未提异议）。
2. 关于页大兔子 → 大肥鱼（鲸鱼吉祥物）。页面主体是 launcher 图标（ic_launcher）+ EmojiBurstHost 彩蛋，
   把 launcher 图标换成本地鲸鱼矢量 Composable（复用 WhaleGirl 系列），保留彩蛋交互。
3. app-control 网关加定时任务动作（schedule/list/delete/pause/resume/trigger）——AI 反馈白名单没有它们。
   4. subagent 只能做「不用工具」的活 → 子代理对话应继承父助手工具面。
   （4 单独 patch： LocalTools 的 getTools 分支已含 subagent 工具本身，但子对话的 assistant 未继承工具开关，
   在 executeRun 创建子 assistant 时 copy 父 assistant 的工具开关字段。）

锚点均取自真实读过的代码。
'''
from pathlib import Path
import re

ROOT = Path.cwd()
CS = "app/src/main/java/me/rerere/rikkahub/service/ChatService.kt"
ABOUT = "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingAboutPage.kt"
MARK = "rhBatch46"


def fail(path, msg):
    print('::error file=' + path + '::batch46 ' + str(msg)[:1500])
    raise SystemExit(1)


# ============================================================
# 1. 回滚 batch41（恢复官方压缩行为）
# ============================================================
t = (ROOT / CS).read_text(encoding='utf-8')
if 'rhCompressFix' in t:
    # --- 回滚 1: 删 compressionJobs 字段 ---
    t = re.sub(
        r'\n    // rhCompressFix: 手动压缩跑在 appScope.*?\n    private val compressionJobs = ConcurrentHashMap<Uuid, Job>\(\)\n',
        '\n', t, count=1, flags=re.S)
    # --- 回滚 2: 删 compressConversationAsync 里的登记 ---
    t = re.sub(
        r'\n        // rhCompressFix: 登记本会话进行中的压缩 job.*?\n        \}\n',
        '\n', t, count=1, flags=re.S)
    # --- 回滚 3: 删 stopGeneration 里的取消 ---
    t = re.sub(
        r'\n        // rhCompressFix: 用户主动停止.*?\n        compressionJobs\[conversationId\]\?\.let \{ runCatching \{ it\.cancelAndJoin\(\) \} \}\n',
        '\n', t, count=1, flags=re.S)
    # --- 回滚 4: 压缩重试回滚为直接调用 ---
    t = re.sub(
        r'                        // rhCompressAB\(B\).*?\n                            out\n                        \}\n',
        '                        async(Dispatchers.IO) {\n                            compressSources(group, requestedTargetTokens)\n                        }\n                    }.awaitAll()\n',
        t, count=1, flags=re.S)
    # --- 回滚 5: 删空 summaries 检查（恢复官方直抛） ---
    t = re.sub(
        r'\n            if \(summaries\.isEmpty\(\)\) \{\n                throw IllegalStateException\("Failed to generate compressed summary \(all groups failed\)"\)\n            \}\n',
        '\n', t, count=1)
    # --- 回滚 6: 强制收敛 → 回官方 partitionSources 原版 ---
    t = re.sub(
        r'            // rhCompressAB\(A\).*?\n            check\(reductionPasses <= 12\) \{\n                "Compression model did not reduce the conversation enough to merge its summaries"\n            \}\n',
        '''            sourceGroups = ContextCompactionPlanner.partitionSources(
                sources = summaries,
                maxInputTokens = mapInputBudgetTokens,
            )
            reductionPasses++
            check(reductionPasses <= 12) {
                "Compression model did not reduce the conversation enough to merge its summaries"
            }
''',
        t, count=1, flags=re.S)

    # 自检：batch41 痕迹应清除
    for token in ['rhCompressFix', 'rhCompressAB', 'compressionJobs', 'all groups failed']:
        if token in t:
            fail(CS, 'rollback incomplete, still has: ' + token)
    (ROOT / CS).write_text(t, encoding='utf-8')
    print('batch46: batch41 rollback OK')
else:
    print('batch46: batch41 not present, skip rollback')


# ============================================================
# 2. 关于页：大兔子 → 鲸鱼（复用 WhaleGirl 系列）
# ============================================================
a = (ROOT / ABOUT).read_text(encoding='utf-8')
if 'rhWhaleAbout' not in a:
    # 2a. import
    for imp in [
        'import me.rerere.rikkahub.ui.components.ui.WhaleGirlPortrait\n',
    ]:
        if imp not in a:
            anchor = 'import me.rerere.rikkahub.ui.theme.CustomColors\n'
            i = a.find(anchor)
            if i < 0:
                fail(ABOUT, 'import anchor CustomColors not found')
            a = a[:i] + imp + a[i:]

    # 2b. 替换 launcher 图标为鲸鱼矢量（保留点击彩蛋）
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
    NEW = '''                        // rhWhaleAbout: 关于页用大肥鱼替代 launcher 图标（可点击触发彩蛋）
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
                            WhaleGirlPortrait(
                                state = MiffanMascotState.Idle,
                                interactive = false,
                                modifier = Modifier.fillMaxSize(),
                            )
                        }'''
    if OLD not in a:
        fail(ABOUT, 'launcher AsyncImage anchor not found')
    a = a.replace(OLD, NEW, 1)

    # Box/MiffanMascotState import
    if 'import androidx.compose.foundation.layout.Box' not in a:
        anchor = 'import androidx.compose.foundation.layout.Column\n'
        i = a.find(anchor)
        if i < 0:
            fail(ABOUT, 'Box import anchor not found')
        a = a[:i] + 'import androidx.compose.foundation.layout.Box\n' + a[i:]
    if 'import me.rerere.rikkahub.ui.components.ui.MiffanMascotState' not in a:
        anchor = 'import me.rerere.rikkahub.ui.components.ui.WhaleGirlPortrait\n'
        a = a.replace(anchor, anchor + 'import me.rerere.rikkahub.ui.components.ui.MiffanMascotState\n', 1)

    (ROOT / ABOUT).read_text()  # touch
    (ROOT / ABOUT).write_text(a, encoding='utf-8')
    print('batch46: about page whale OK')
else:
    print('batch46: about page already whale')


print('batch46: PART 1+2 OK')
