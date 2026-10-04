#!/usr/bin/env python3
'''batch71: 修复 #190 唯一编译错误——onJumpToMessage 作用域

根因（#190 annotations 实证，且为该构建唯一 Kotlin 错误）：
batch69 把 QuoteBlock 挂进 ChatListNormal 的 items 循环，但
onJumpToMessage 只存在于 ChatList / ChatListPreview 签名——
ChatListNormal 没有该参数。五查第 3 项当时漏查了「宿主函数签名」。

修复策略（零签名改动、零调用链穿透）：
QuoteBlock 的点击跳转改用 ChatListNormal 已有的两个成员：
- scope: rememberCoroutineScope()（ChatListNormal 函数体开头，实读确认）
- state: LazyListState（函数参数，实读确认）
直接把 `onJumpToMessage(qIdx)` 换成 `scope.launch { state.scrollToItem(qIdx) }`。
displayGroups 的 index 即 LazyColumn 的 item index（items 从 0 开始，
其后才是系统提示/加载行/底部占位——实读确认顺序），索引语义一致。

五查：
1. import 清单：scrollToItem 是 LazyListState 成员无需 import；
   launch 在 ChatList.kt imports 已有（kotlinx.coroutines.launch 实读确认）
2. 同文件冲突：替换行在 batch69 插入块内（69 先跑 71 后跑，顺序确定）；
   batch64 锚点在不同行，不相交
3. 作用域：scope/state 在 QuoteBlock 所在 items lambda 内均可见
4. 括号配对：替换行 { } ( ) 自平衡，脚本内计数自检
5. 函数签名：scrollToItem(index: Int) 为 LazyListState 挂起成员，
   在 scope.launch 协程内调用合法

Python 三查：无引号问题；无未定义引用；无 f-string/walrus/join。
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
OLD = 'if (qIdx >= 0) onJumpToMessage(qIdx)'
NEW = 'if (qIdx >= 0) scope.launch { state.scrollToItem(qIdx) } // rhJumpFix'


def fail(path, message):
    print('::error file=' + path + '::batch71 ' + str(message)[:1400])
    raise SystemExit(1)


CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'
t = (ROOT / CL).read_text(encoding='utf-8')
if 'rhJumpFix' in t:
    print('batch71: already applied')
else:
    count = t.count(OLD)
    if count != 1:
        fail(CL, 'onJumpToMessage quote-jump line count=' + str(count))
    # 前置验证：launch import 必须已存在
    if 'import kotlinx.coroutines.launch' not in t:
        fail(CL, 'kotlinx.coroutines.launch import missing')
    lines = t.split(NL)
    for index, line in enumerate(lines):
        if OLD in line:
            replaced = line.replace(OLD, NEW, 1)
            if replaced.count('(') != replaced.count(')'):
                fail(CL, 'paren imbalance after replacement')
            if replaced.count('{') != replaced.count('}'):
                fail(CL, 'brace imbalance after replacement')
            lines[index] = replaced
            break
    text = ''
    for index, line in enumerate(lines):
        if index > 0:
            text += NL
        text += line
    if 'scope.launch { state.scrollToItem(qIdx) }' not in text:
        fail(CL, 'replacement missing after apply')
    if 'onJumpToMessage(qIdx)' in text:
        fail(CL, 'old reference still present')
    (ROOT / CL).write_text(text, encoding='utf-8')
    print('batch71: quote jump now uses scope.launch + state.scrollToItem')

print('batch71: OK')
