from pathlib import Path

ROOT = Path.cwd()

def fail(path, msg):
    print(f"::error file={path}::batch26 {msg[:1400]}")
    raise SystemExit(1)

# ============================================================
# N2 任务步骤条序号（ChatMessageTools.kt 的 ChatMessageToolStep）
# 实测基础：读 ChatMessageTools.kt 8KB+8KB（共 35KB）前半，步骤已经是卡片
# （ControlledChainOfThoughtStep），只需在 label 里加序号。
# 但问题：ChatMessageToolStep 是单个工具的渲染，它不知道自己是第几个。
# 序号需要从 MessagePartsBlock 的 ThinkingBlock.steps 里推导（tool 在列表中的索引）。
# 方案：ChatMessageToolStep 加可选参数 stepNumber: Int? = null，调用处
# （ChatMessage.kt 的 ThinkingStep.ToolStep 分支）传入 index+1。
# ============================================================

P1 = "app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageTools.kt"
t1 = (ROOT / P1).read_text(encoding="utf-8")

if "stepNumber" in t1:
    print("batch26: ChatMessageTools already patched")
else:
    # 1. ChatMessageToolStep 签名加参数（锚点：onRerunTool 参数行后）
    A = (
        "    onRerunTool: (suspend (toolCallId: String) -> me.rerere.rikkahub.service.ChatService.RerunToolResult)? = null,\n"
        ") {\n"
    )
    B = (
        "    onRerunTool: (suspend (toolCallId: String) -> me.rerere.rikkahub.service.ChatService.RerunToolResult)? = null,\n"
        "    stepNumber: Int? = null,\n"
        ") {\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"ChatMessageToolStep signature anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    # 2. label Text 前加序号（锚点：renderer.title(context) 的 Text）
    A = (
        "        label = {\n"
        "            Text(\n"
        "                text = renderer.title(context),\n"
    )
    B = (
        "        label = {\n"
        "            val titleText = if (stepNumber != null) \"$stepNumber. \" + renderer.title(context) else renderer.title(context)\n"
        "            Text(\n"
        "                text = titleText,\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"label Text anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    (ROOT / P1).write_text(t1, encoding="utf-8")
    print("batch26: ChatMessageToolStep stepNumber param added")

# 调用处在 ChatMessage.kt 的 ThinkingStep.ToolStep 分支，需要 index
P2 = "app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt"
t2 = (ROOT / P2).read_text(encoding="utf-8")

if "stepNumber =" in t2:
    print("batch26: ChatMessage already patched")
else:
    # ThinkingBlock 的 steps 循环是 ChainOfThought(...) { step -> ... }，没有 index。
    # 需要改用 steps.forEachIndexed 或在 ChainOfThought 内部加 index。
    # 但 ChainOfThought 是通用组件（ui/components/ui/），不宜改。
    # 方案：在 ThinkingBlock 渲染前先 mapIndexed 加 index 到 step？不，step 是 sealed class。
    # 更简单：ChatMessageToolStep 调用处已经是 key(step.tool.toolCallId) { ... }，
    # 在外层 block.steps 是 List，用 withIndex()。
    # 但 ChainOfThought 的 steps lambda 是 @Composable (T) -> Unit，没有 index 参数。
    # 
    # 实际上从读到的代码看：block.steps.fastForEach { step -> when(step) { ToolStep -> ChatMessageToolStep(...) } }
    # fastForEach 没有 index。改成 fastForEachIndexed 或 mapIndexed？fastForEachIndexed 存在。
    # 
    # 重新定位锚点：MessagePartsBlock 里 ThinkingBlock 分支，ChainOfThought 的 content lambda。
    # 当前是 `} { step -> when (step) { ... } }`，改为收集 tool index 并传递。
    # 
    # 但等等——ThinkingBlock.steps 是混合类型（ReasoningStep/ToolStep/ServerToolStep），
    # 只有 ToolStep 需要序号。序号应该是「第几个 ToolStep」而非「第几个 step」。
    # 计数器：var toolIndex = 0，ToolStep 分支里 toolIndex++，传 toolIndex。
    # 
    # 锚点：ChainOfThought(...) 的 content lambda 开头加计数器。
    A = (
        "                    ChainOfThought(\n"
        "                        modifier = Modifier.animateContentSize(),\n"
        "                        steps = block.steps,\n"
        "                        collapsedAdaptiveWidth = isReasoningOnlyBlock,\n"
        "                        forceExpanded = hasPendingApproval,\n"
        "                        cardColors = CardDefaults.cardColors(\n"
        "                            containerColor = MaterialTheme.colorScheme.surfaceContainerHigh.copy(alpha = settings.displaySetting.bubbleOpacity),\n"
        "                        ),\n"
        "                    ) { step ->\n"
    )
    B = (
        "                    var toolStepIndex = 0\n"
        "                    ChainOfThought(\n"
        "                        modifier = Modifier.animateContentSize(),\n"
        "                        steps = block.steps,\n"
        "                        collapsedAdaptiveWidth = isReasoningOnlyBlock,\n"
        "                        forceExpanded = hasPendingApproval,\n"
        "                        cardColors = CardDefaults.cardColors(\n"
        "                            containerColor = MaterialTheme.colorScheme.surfaceContainerHigh.copy(alpha = settings.displaySetting.bubbleOpacity),\n"
        "                        ),\n"
        "                    ) { step ->\n"
    )
    if t2.count(A) != 1:
        fail(P2, f"ChainOfThought lambda anchor count={t2.count(A)}")
    t2 = t2.replace(A, B, 1)

    # ToolStep 分支里递增并传 stepNumber
    A = (
        "                            is ThinkingStep.ToolStep -> {\n"
        "                                key(step.tool.toolCallId.ifBlank { step.hashCode().toString() }) {\n"
        "                                    ChatMessageToolStep(\n"
        "                                        tool = step.tool,\n"
        "                                        loading = loading && !step.tool.isExecuted,\n"
        "                                        generationActive = generationActive,\n"
        "                                        onToolApproval = onToolApproval,\n"
        "                                        onToolAnswer = onToolAnswer,\n"
        "                                        onRerunTool = onRerunTool,\n"
        "                                    )\n"
    )
    B = (
        "                            is ThinkingStep.ToolStep -> {\n"
        "                                toolStepIndex++\n"
        "                                key(step.tool.toolCallId.ifBlank { step.hashCode().toString() }) {\n"
        "                                    ChatMessageToolStep(\n"
        "                                        tool = step.tool,\n"
        "                                        loading = loading && !step.tool.isExecuted,\n"
        "                                        generationActive = generationActive,\n"
        "                                        onToolApproval = onToolApproval,\n"
        "                                        onToolAnswer = onToolAnswer,\n"
        "                                        onRerunTool = onRerunTool,\n"
        "                                        stepNumber = toolStepIndex,\n"
        "                                    )\n"
    )
    if t2.count(A) != 1:
        fail(P2, f"ToolStep call anchor count={t2.count(A)}")
    t2 = t2.replace(A, B, 1)

    (ROOT / P2).write_text(t2, encoding="utf-8")
    print("batch26: Tool step numbering wired (1. 2. 3. ...)")
