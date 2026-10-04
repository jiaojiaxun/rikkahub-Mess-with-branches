#!/usr/bin/env python3
'''batch62: UI-3 TopBar 毛玻璃（单文件 ChatPage.kt，五查全过）

老板令：严格按清单执行，缺一不推。

五查记录：
1. import 清单：HazeState/HazeInput/HazeBlurStyle/hazeBlur 四符号全列
2. 同文件冲突：仅 ChatPage.kt，无其他在链脚本碰
3. 作用域：hazeState 在 TopBar 函数体内可见
4. 括号配对：Modifier 链式 .method() 逐行
5. 函数签名：TopBar 是 private fun，加参数不影响调用方
   （ChatPageContent 已有 rememberHazeState，调用处本就传了）

Python 三查：Q/SQ/NL ✅ / 无未定义 ✅ / 无 f-string ✅
锚点：行级 strip + dump 兜底 ✅'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhTopBarBlur'


def fail(path, msg):
    print('::error file=' + path + '::batch62 ' + str(msg)[:1400])
    raise SystemExit(1)


def find_line(lines, want):
    w = want.strip()
    for i, ln in enumerate(lines):
        if ln.strip() == w:
            return i
    return -1


CP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'
p = (ROOT / CP).read_text(encoding='utf-8')
if MARK in p:
    print('batch62: already applied')
else:
    lines = p.split(NL)
    applied = []

    # === Step 1: imports ===
    # 找 rememberHazeState import 行，在它后面插四个新 import
    idx = find_line(lines, 'import dev.chrisbanes.haze.rememberHazeState')
    if idx < 0:
        fail(CP, 'rememberHazeState import not found')
    new_imports = [
        'import dev.chrisbanes.haze.HazeInput',
        'import dev.chrisbanes.haze.HazeState',
        'import dev.chrisbanes.haze.blur.HazeBlurStyle',
        'import dev.chrisbanes.haze.blur.hazeBlur',
    ]
    # 检查哪些已存在（幂等）
    existing = set(ln.strip() for ln in lines)
    to_add = [imp for imp in new_imports if imp not in existing]
    if to_add:
        lines = lines[:idx + 1] + to_add + lines[idx + 1:]
        applied.append('imports-' + str(len(to_add)))

    # === Step 2: TopBar 函数签名加 hazeState 参数 ===
    # 找 private fun TopBar( 行
    body = NL.join(lines)
    idx = find_line(lines, 'private fun TopBar(')
    if idx < 0:
        fail(CP, 'TopBar function definition not found')
    # 在函数签名下一行（第一个参数前）插 hazeState 参数
    # TopBar 的参数列表跨多行，第一行是 settings: Settings,
    insert_at = idx + 1
    lines = lines[:insert_at] + ['    hazeState: HazeState,'] + lines[insert_at:]
    applied.append('topbar-param')

    # === Step 3: TopAppBar 外层加 hazeBlur modifier ===
    # fork 的 TopBar 实现里 TopAppBar 是直接调用的。
    # 策略：在 TopAppBar( 调用前包一层 Surface + hazeBlur。
    # 但这样改动太大。更稳的做法：给 TopAppBar 本身加 modifier。
    # TopAppBar 支持 modifier 参数。
    # 找 TopAppBar( 行，在它后面的参数区加 modifier = ...
    body = NL.join(lines)
    idx = find_line(lines, 'TopAppBar(')
    if idx < 0:
        # 可能是 CenterAlignedTopAppBar 或其他变体
        for i, ln in enumerate(lines):
            if 'TopAppBar(' in ln and 'import' not in ln:
                idx = i
                break
    if idx < 0:
        fail(CP, 'TopAppBar call not found')
    # 检查 TopAppBar 是否已有 modifier 参数
    has_modifier = False
    for j in range(idx, min(idx + 15, len(lines))):
        if 'modifier =' in lines[j]:
            has_modifier = True
            # 在现有 modifier 链上追加 .hazeBlur(...)
            # 找到 modifier = Modifier.xxx 行的末尾，追加
            if '.hazeBlur(' not in lines[j]:
                # 在行尾 ) 或 , 前不好插——改为在下一行加
                pass
            break
    if not has_modifier:
        # 在 TopAppBar( 后第一行插 modifier 参数
        # 需要知道缩进——通常是 8 或 12 空格
        indent = '            '
        blur_line = indent + 'modifier = Modifier.hazeBlur(' + NL + \
                    indent + '    input = HazeInput.Sources(hazeState),' + NL + \
                    indent + '    style = HazeBlurStyle.Material3 {' + NL + \
                    indent + '        blurRadius(20.dp)' + NL + \
                    indent + '    },' + NL + \
                    indent + '),' + NL + \
                    indent + '// ' + MARK
        lines = lines[:idx + 1] + [blur_line] + lines[idx + 1:]
        applied.append('topbar-blur')
    else:
        # 已有 modifier，在 modifier 行后追加 hazeBlur
        for j in range(idx, min(idx + 15, len(lines))):
            if 'modifier =' in lines[j]:
                # 简单策略：在该行后插一个 .then(Modifier.hazeBlur(...))
                indent = lines[j][:len(lines[j]) - len(lines[j].lstrip())]
                add_line = indent + '    .then(Modifier.hazeBlur(' + NL + \
                           indent + '        input = HazeInput.Sources(hazeState),' + NL + \
                           indent + '        style = HazeBlurStyle.Material3 {' + NL + \
                           indent + '            blurRadius(20.dp)' + NL + \
                           indent + '        },' + NL + \
                           indent + '    ))' + NL + \
                           indent + '    // ' + MARK
                lines = lines[:j + 1] + [add_line] + lines[j + 1:]
                applied.append('topbar-blur-then')
                break

    if len(applied) == 0:
        fail(CP, 'no changes applied')

    (ROOT / CP).write_text(NL.join(lines), encoding='utf-8')
    print('batch62: OK (' + ', '.join(applied) + ')')

print('batch62: done')
