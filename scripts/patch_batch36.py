#!/usr/bin/env python3
"""batch36: 聊天页吉祥物叠层

目标（用户要求"间接体现 + 高度一致"）：
mascotEnabled 打开时，聊天页右下角浮动吉祥物，状态实时跟随
errors / loadingJob，让吉祥物从"设置页可见"升级为"聊天页可见"。
不新增页面，不加突兀控件，复用 Material3 布局与现有 Settings 开关。

锚点（已用 API 读到 ChatPage.kt 真实源码，逐字节精确匹配）：
  head:  '        ) { innerPadding ->\n            ChatList(\n'
  tail:  onConversationSystemPromptChange ... )\n        }\n

import 前置核查（ChatPage.kt 现有）：
  ✅ Box / fillMaxSize / dp
  ❌ Alignment / padding / size / WhaleGirlMascot / MiffanMascotState -> 脚本补

铁律：不用 f-string；含 Kotlin 双引号的块用 Python 单引号字符串；幂等标记 rhWhalePresetChat
"""
from pathlib import Path

ROOT = Path.cwd()
MARK = "rhWhalePresetChat"


def fail(path, msg):
    print('::error file=' + path + '::batch36 ' + msg[:1400])
    raise SystemExit(1)


P_CHAT = "app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt"
t = (ROOT / P_CHAT).read_text(encoding="utf-8")

if MARK in t:
    print("batch36: ChatPage already has mascot overlay")
else:
    # --- 1. ChatList 尾部锚点（精确字节）---
    ANCHOR_TAIL = (
        '                onConversationSystemPromptChange = { newPrompt ->\n'
        '                    vm.updateConversation(conversation.copy(customSystemPrompt = newPrompt))\n'
        '                    vm.saveConversationAsync()\n'
        '                },\n'
        '            )\n'
        '        }\n'
    )
    idx = t.find(ANCHOR_TAIL)
    if idx < 0:
        fail(P_CHAT, "ChatList tail anchor not found (source changed?)")

    # --- 2. ChatList 头部锚点 ---
    ANCHOR_HEAD = '        ) { innerPadding ->\n            ChatList(\n'
    hidx = t.find(ANCHOR_HEAD)
    if hidx < 0:
        fail(P_CHAT, "ChatList head anchor not found (source changed?)")

    # 头：包一层 Box（缩进 +4 给 ChatList 的参数列，这里只改包裹层，
    # ChatList 自身参数缩进保持原样也能编译——Kotlin 不关心缩进）
    new_head = (
        '        ) { innerPadding ->\n'
        '            Box(modifier = Modifier.fillMaxSize()) {\n'
        '            ChatList(\n'
    )
    t = t[:hidx] + new_head + t[hidx + len(ANCHOR_HEAD):]

    # 尾：ChatList 闭合后插叠层，再补 Box 闭合
    new_tail = (
        '                onConversationSystemPromptChange = { newPrompt ->\n'
        '                    vm.updateConversation(conversation.copy(customSystemPrompt = newPrompt))\n'
        '                    vm.saveConversationAsync()\n'
        '                },\n'
        '            )\n'
        '            if (setting.displaySetting.mascotEnabled) {\n'
        '                WhaleGirlMascot(\n'
        '                    state = if (errors.isNotEmpty()) {\n'
        '                        MiffanMascotState.Error\n'
        '                    } else if (loadingJob != null) {\n'
        '                        MiffanMascotState.Thinking\n'
        '                    } else {\n'
        '                        MiffanMascotState.Idle\n'
        '                    },\n'
        '                    interactive = true,\n'
        '                    presentation = MiffanPresentation.Avatar,\n'
        '                    modifier = Modifier\n'
        '                        .align(Alignment.BottomEnd)\n'
        '                        .padding(end = 12.dp, bottom = 12.dp)\n'
        '                        .size(96.dp),\n'
        '                )\n'
        '            }\n'
        '            }\n'
        '        }\n'
    )
    idx2 = t.find(ANCHOR_TAIL)
    if idx2 < 0:
        fail(P_CHAT, "ChatList tail anchor lost after head replace")
    t = t[:idx2] + new_tail + t[idx2 + len(ANCHOR_TAIL):]

    # --- 3. import 补齐（只补缺失的）---
    def add_import(src, anchor, addition):
        if addition in src:
            return src
        return src.replace(anchor, anchor + "\n" + addition, 1)

    t = add_import(t, "import androidx.compose.foundation.layout.fillMaxWidth",
                   "import androidx.compose.foundation.layout.padding")
    t = add_import(t, "import androidx.compose.foundation.layout.fillMaxWidth",
                   "import androidx.compose.foundation.layout.size")
    t = add_import(t, "import androidx.compose.ui.Modifier",
                   "import androidx.compose.ui.Alignment")
    t = add_import(t, "import me.rerere.rikkahub.ui.components.ui.permission.PermissionCamera",
                   "import me.rerere.rikkahub.ui.components.ui.WhaleGirlMascot")
    t = add_import(t, "import me.rerere.rikkahub.ui.components.ui.permission.PermissionCamera",
                   "import me.rerere.rikkahub.ui.components.ui.MiffanMascotState")
    t = add_import(t, "import me.rerere.rikkahub.ui.components.ui.permission.PermissionCamera",
                   "import me.rerere.rikkahub.ui.components.ui.MiffanPresentation")

    (ROOT / P_CHAT).write_text(t, encoding="utf-8")
    print("batch36: ChatPage mascot overlay added")

print("batch36: OK")
