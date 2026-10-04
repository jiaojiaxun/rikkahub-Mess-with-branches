#!/usr/bin/env python3
'''batch82: R4 顶栏形状适配——顶部直角+底部圆角（材质完全复制输入框）

背景：batch80v6 已复制输入框材质（surfaceContainerLow + outlineVariant@50% +
largeIncreased 圆角）。但顶栏贴边，完整圆角会在顶部两角露出背景色。

改法：shape 保留 largeIncreased 的底部圆角，把顶部两角置 0（贴边不露背景）。
材质（色调/描边/tonalElevation）与输入框完全一致 → "复制输入框的玻璃效果"。

五查：
1. import：需 CornerSize（androidx.compose.foundation.shape.CornerSize）
   ——脚本确保存在：锚 import androidx.compose.foundation.BorderStroke（batch80v6 插入，count=1）
2. 同文件冲突：ChatPage.kt 被 batch62/63/80v6 碰过；锚点在 rhTopBarAlignInput 之后
3. 作用域：TopBar @Composable 内 Surface 参数 ✅
4. 括号配对：单行 shape 表达式替换，圆括号自平衡（copy( 与 ) 同行）
5. 函数签名：不改

Python 三查：无引号字面量 / 无未定义引用 / 无 f-string
'''
from pathlib import Path
ROOT = Path.cwd()
NL = chr(10)
M = 'rhTopBarShape'

def fail(p, m):
    print('::error file=' + p + '::batch82 ' + str(m)[:1200])
    raise SystemExit(1)

def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]

CP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'
t = (ROOT / CP).read_text(encoding='utf-8')
if M in t:
    print('batch82: already applied')
else:
    lines = t.split(NL)

    # 1. 确保 CornerSize import 存在
    if 'import androidx.compose.foundation.shape.CornerSize' not in t:
        anchor = [i for i, ln in enumerate(lines) if ln.strip() == 'import androidx.compose.foundation.BorderStroke']
        if len(anchor) != 1:
            fail(CP, 'BorderStroke import anchor count=' + str(len(anchor)))
        lines.insert(anchor[0] + 1, 'import androidx.compose.foundation.shape.CornerSize')
        print('batch82: CornerSize import added')

    # 2. 定位 rhTopBarAlignInput 的 Surface，替换其 shape 行
    mark_idx = [i for i, ln in enumerate(lines) if 'rhTopBarAlignInput' in ln]
    if len(mark_idx) != 1:
        fail(CP, 'rhTopBarAlignInput marker count=' + str(len(mark_idx)))
    mi = mark_idx[0]
    shape_idx = -1
    for i in range(mi, min(mi + 10, len(lines))):
        if lines[i].strip() == 'shape = MaterialTheme.shapes.largeIncreased,':
            shape_idx = i
            break
    if shape_idx < 0:
        print('batch82: dump after marker:')
        for i in range(mi, min(mi + 12, len(lines))):
            print('  >> ' + str(i) + ': ' + lines[i].strip()[:150])
        fail(CP, 'shape line not found after rhTopBarAlignInput marker')
    d = ind(lines[shape_idx])
    lines[shape_idx] = d + 'shape = MaterialTheme.shapes.largeIncreased.copy(topStart = CornerSize(0.dp), topEnd = CornerSize(0.dp)), // ' + M
    t = NL.join(lines)
    # 3. 自检
    if M not in t:
        fail(CP, 'marker missing after apply')
    if 'CornerSize(0.dp)' not in t:
        fail(CP, 'CornerSize override missing')
    if 'import androidx.compose.foundation.shape.CornerSize' not in t:
        fail(CP, 'CornerSize import missing')
    (ROOT / CP).write_text(t, encoding='utf-8')
    print('batch82: OK (top corners flat, bottom rounded, material copied)')

print('batch82: done')
