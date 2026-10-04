#!/usr/bin/env python3
'''batch73: 补 ChatPage.kt 缺失的 UIMessage import（单行修复）

#196 死因（编译，非 patch）：ChatPage.kt:343 Unresolved reference 'UIMessage'
+ 级联 4 错（toText on Any / id 未解析 x2 / 泛型推断失败）。
根因：batch70 的 import 检查用子串匹配 'import me.rerere.ai.ui.UIMessage' in page，
而该串是 'import me.rerere.ai.ui.UIMessagePart' 的前缀 → 误判已存在 → 跳过插入。
五查第 1 项（import 清单）的检查逻辑本身失守。

包路径正确性证据：ChatMessage.kt 的 import 表实读含
import me.rerere.ai.ui.UIMessage 且 #190 编译通过 → 路径正确。

幂等场景说明：batch70 的 MARK（rhQuoteSend）已在 ChatPage 里（#196 patch 成功），
重推 batch70 会整段跳过。本脚本独立检查 import 行，只补 import，不动其他。

五查：
1. import 清单：本脚本自身只引入一个 import 行；检查逻辑改为
   精确行匹配（strip 后全等）——铁律 20
2. 同文件冲突：ChatPage.kt 被 batch70 改过（引用条/状态/接线），
   本脚本只插 import 区一行（锚点 UIMessagePart import 行，batch70 未碰 import 区）
3. 作用域：import 在文件顶部，全局可见
4. 括号配对：单行插入，零括号改动
5. 函数签名：无签名改动

Python 三查：无引号字面量 / 无未定义引用 / 无 f-string/walrus/join。
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
IMPORT_LINE = 'import me.rerere.ai.ui.UIMessage'
ANCHOR_LINE = 'import me.rerere.ai.ui.UIMessagePart'


def concat_lines(lines):
    text = ''
    for index, line in enumerate(lines):
        if index > 0:
            text += NL
        text += line
    return text


def fail(path, message):
    print('::error file=' + path + '::batch73 ' + str(message)[:1400])
    raise SystemExit(1)


CP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'
page = (ROOT / CP).read_text(encoding='utf-8')
lines = page.split(NL)

# 精确行匹配检查（铁律 20：不用 in 子串）
has_import = False
for line in lines:
    if line.strip() == IMPORT_LINE:
        has_import = True
        break

if has_import:
    print('batch73: UIMessage import already present (exact-line match)')
else:
    anchors = []
    for index, line in enumerate(lines):
        if line.strip() == ANCHOR_LINE:
            anchors.append(index)
    if len(anchors) != 1:
        fail(CP, 'UIMessagePart import anchor count=' + str(len(anchors)))
    lines.insert(anchors[0] + 1, IMPORT_LINE)

    text = concat_lines(lines)
    # 自检：插入后精确行必须存在且唯一
    count = 0
    for line in text.split(NL):
        if line.strip() == IMPORT_LINE:
            count += 1
    if count != 1:
        fail(CP, 'UIMessage import count after insert=' + str(count))
    (ROOT / CP).write_text(text, encoding='utf-8')
    print('batch73: UIMessage import inserted after UIMessagePart')

print('batch73: OK')
