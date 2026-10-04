#!/usr/bin/env python3
'''batch55-4b-fix: ChatDrawer.kt 的 ConversationList 调用处传 getChildren 参数

问题：batch55-4b v2 只改了 ChatDrawerVM + ConversationList，没改 ChatDrawer.kt
ConversationList 调用处未传 getChildren 参数——折叠树不会生效（编译过但功能不生效）

修复：在 ChatDrawer.kt 的 ConversationList 调用处传 getChildren 参数
锚点：ConversationList( 调用行（子串匹配）

五查：
1. import：ChatDrawer.kt 已有 Flow 相关 import（collectAsStateWithLifecycle）
2. 同文件冲突：ChatDrawer.kt 被 batch74v4 碰过——锚点在 ConversationList 调用处未被碰
3. 作用域：ChatDrawerContent 是 @Composable，drawerVm.getChildrenFlow 合法
4. 括号配对：参数行插入，自平衡
5. 函数签名：无改动

Python 三查：无引号字面量 / 无未定义引用 / 无 f-string/walrus/join
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhFoldTree'


def concat_lines(lines):
    t = ''
    for idx, ln in enumerate(lines):
        if idx > 0:
            t += NL
        t += ln
    return t


def fail(path, msg):
    print('::error file=' + path + '::batch55-4b-fix ' + str(msg)[:1400])
    raise SystemExit(1)


def indent_of(line):
    return line[:len(line) - len(line.lstrip())]


CD = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatDrawer.kt'
cd = (ROOT / CD).read_text(encoding='utf-8')
if MARK not in cd:
    lines = cd.split(NL)
    applied = []

    # 找 ConversationList( 调用行（子串匹配，且行内只有 ConversationList(）
    conv_indices = []
    for idx, ln in enumerate(lines):
        s = ln.strip()
        if s == 'ConversationList(':
            conv_indices.append(idx)
    if len(conv_indices) != 1:
        print('batch55-4b-fix: dump ConversationList candidates:')
        for idx, ln in enumerate(lines):
            if 'ConversationList' in ln:
                print('  >> line ' + str(idx) + ': ' + ln.strip()[:160])
        fail(CD, 'ConversationList( anchor count=' + str(len(conv_indices)))
    ci = conv_indices[0]
    ind = indent_of(lines[ci])
    # 在 ConversationList( 之后插入 getChildren 参数
    # 找 ConversationList( 的结束（下一个 ) 或参数行）
    # 简化：在 ConversationList( 之后的第一行插入
    lines.insert(ci + 1, ind + '    getChildren = { parentId -> drawerVm.getChildrenFlow(parentId) }, // ' + MARK)
    applied.append('getChildren')

    text = concat_lines(lines)
    if 'getChildren = { parentId -> drawerVm.getChildrenFlow(parentId) }' not in text:
        fail(CD, 'getChildren param missing after apply')
    (ROOT / CD).write_text(text, encoding='utf-8')
    print('batch55-4b-fix: ChatDrawer OK (' + ', '.join(applied) + ')')
else:
    print('batch55-4b-fix: ChatDrawer already applied')

print('batch55-4b-fix: OK')
