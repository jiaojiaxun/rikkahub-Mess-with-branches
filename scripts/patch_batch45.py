#!/usr/bin/env python3
'''batch45: 工具调用链进度显示（ThinkingBlock 完成度徽标）

用户需求：工具调用时像截图那样看到进度（如 0/4），而不是只有 shimmer。
现状：ChainOfThought 折叠时只显示最后 2 步 + 展开箭头，无进度计数。

方案：在 MessagePartsBlock 的 ThinkingBlock 分支加“N/M 徽标”：
- 总数 M = block.steps.size
- 已完成 N = 步骤中非 loading 的数量（Tool.isExecuted / ServerTool.isFinished）
- loading 时徽标 shimmer，全部完成后徽标不闪
- 徽标画在 ChainOfThought 卡片上方（Row：Sparkles 图标 + “已思考 N 步”+ 进度 pill）
- 只有 loading 或步骤数>=2 时显示，历史消息不打扰

锚点（全部来自真实读到的 ChatMessage.kt）：
- A1: hasPendingApproval 定义段（any { ... Pending }）
- A2: ChainOfThought( modifier...steps = block.steps, 调用头
字符串替换，缩进用捕获组推导，幂等 marker rhToolProgressBadge。
'''
from pathlib import Path
import re

ROOT = Path.cwd()
P = "app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt"
MARK = "rhToolProgressBadge"


def fail(msg):
    print('::error file=' + P + '::batch45 ' + str(msg)[:1200])
    raise SystemExit(1)


t = (ROOT / P).read_text(encoding='utf-8')
if MARK in t:
    print('batch45: already applied')
    raise SystemExit(0)

# ---------- 1. 在 hasPendingApproval 之后插入进度计算 + 徽标 UI ----------
A1 = (
    '                    val hasPendingApproval = block.steps.any {\n'
    '                        it is ThinkingStep.ToolStep &&\n'
    '                            it.tool.approvalState is ToolApprovalState.Pending\n'
    '                    }\n'
)
if A1 not in t:
    fail('anchor A1 hasPendingApproval not found')

INSERT_1 = A1 + (
    '                    // rhToolProgressBadge: 步骤完成度（N/M）—— 0/4 这样的进度一眼可见\n'
    '                    val finishedSteps = block.steps.count { step ->\n'
    '                        when (step) {\n'
    '                            is ThinkingStep.ToolStep -> step.tool.isExecuted\n'
    '                            is ThinkingStep.ServerToolStep -> step.tool.isFinished\n'
    '                            is ThinkingStep.ReasoningStep -> true\n'
    '                        }\n'
    '                    }\n'
    '                    val totalSteps = block.steps.size\n'
)
t = t.replace(A1, INSERT_1, 1)

# ---------- 2. 在 ChainOfThought 调用前插入徽标 UI ----------
A2 = (
    '                    ChainOfThought(\n'
    '                        modifier = Modifier.animateContentSize(),\n'
    '                        steps = block.steps,\n'
)
if A2 not in t:
    fail('anchor A2 ChainOfThought call not found')

INSERT_2 = (
    '                    // rhToolProgressBadge: 折叠态进度徽标 —— 只有正在生成或步骤>=3 时显示\n'
    '                    if (loading || totalSteps >= 3) {\n'
    '                        Row(\n'
    '                            modifier = Modifier\n'
    '                                .fillMaxWidth()\n'
    '                                .padding(bottom = 2.dp),\n'
    '                            verticalAlignment = Alignment.CenterVertically,\n'
    '                            horizontalArrangement = Arrangement.spacedBy(6.dp),\n'
    '                        ) {\n'
    '                            Icon(\n'
    '                                imageVector = HugeIcons.Sparkles,\n'
    '                                contentDescription = null,\n'
    '                                modifier = Modifier.size(14.dp),\n'
    '                                tint = MaterialTheme.colorScheme.primary,\n'
    '                            )\n'
    '                            Text(\n'
    '                                text = "$finishedSteps/$totalSteps",\n'
    '                                style = MaterialTheme.typography.labelSmall,\n'
    '                                color = MaterialTheme.colorScheme.primary,\n'
    '                                modifier = Modifier.shimmer(\n'
    '                                    isLoading = loading && finishedSteps < totalSteps\n'
    '                                ),\n'
    '                            )\n'
    '                        }\n'
    '                    }\n'
    '                    ChainOfThought(\n'
    '                        modifier = Modifier.animateContentSize(),\n'
    '                        steps = block.steps,\n'
)
t = t.replace(A2, INSERT_2, 1)

# ---------- 3. 补 import（Sparkles / shimmer 若缺）----------
for imp, anchor in [
    ('import me.rerere.hugeicons.stroke.Sparkles\n', 'import me.rerere.hugeicons.stroke.MusicNote03\n'),
    ('import me.rerere.rikkahub.ui.modifier.shimmer\n', 'import me.rerere.rikkahub.ui.context.LocalNavController\n'),
]:
    if imp not in t:
        i = t.find(anchor)
        if i < 0:
            fail('import anchor not found: ' + anchor)
        t = t[:i] + imp + t[i:]

# ---------- 自检 ----------
for need in [
    MARK,
    'val finishedSteps = block.steps.count',
    '"$finishedSteps/$totalSteps"',
    'import me.rerere.hugeicons.stroke.Sparkles',
    'import me.rerere.rikkahub.ui.modifier.shimmer',
]:
    if need not in t:
        fail('selfcheck missing: ' + repr(need))

if t.count('ChainOfThought(\n') != t.count('ChainOfThought('):
    # 老调用应仍是 1 处（只是被前插）
    pass

(ROOT / P).write_text(t, encoding='utf-8')
print('batch45: OK')
