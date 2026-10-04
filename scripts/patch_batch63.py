#!/usr/bin/env python3
'''batch63: 归一化 TopBar Haze 接线，修复 #183 全部 ChatPage 编译错误

#183 annotations 实证（全部位于 ChatPage.kt）：
- line 391  No value passed for parameter hazeState（调用区缺传参）
- line 849/850 Conflicting declarations（定义区两份 hazeState 参数）
- line 870/871 Material3/blurRadius 未解析（用了未导入的 Material3 扩展）

根因链：
1. batch59 的守卫字符串 'hazeState = hazeState,' 命中了 ChatList 调用的
   同名实参（不是 TopBar 调用），于是往 TopBar 定义插了一份带默认值的参数。
2. batch62 无条件下又在 TopBar 定义插了第二份参数。
3. batch62 使用了 HazeBlurStyle.Material3（material3 扩展），但没有导入；
   alpha05 基础 DSL 是 HazeBlurStyle { blurRadius(...) }。

本脚本按结构范围归一化，而不是再追加一行：
- 定义区：删除全部 hazeState 参数，只保留一行必填参数。
- 调用区：删除全部 hazeState 实参，只保留一行。
- API：Material3 DSL 归一化为 alpha05 基础 DSL。
- 全部五查 + Python 三查 + 结构自检在脚本内 fail-fast：
  import 清单 / 同文件冲突 / 作用域 / 括号配对（balanced 扫描）/ 函数签名。
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhTopBarBlurFixed'


def fail(path, msg):
    print('::error file=' + path + '::batch63 ' + str(msg)[:1400])
    raise SystemExit(1)


def balanced_end(lines, start):
    depth = 0
    for i in range(start, len(lines)):
        line = lines[i]
        if i == start:
            pos = line.find('(')
            if pos < 0:
                return -1
            part = line[pos:]
        else:
            part = line
        depth += part.count('(')
        depth -= part.count(')')
        if depth == 0:
            return i
        if depth < 0:
            return -1
    return -1


def leading_spaces(line):
    return line[:len(line) - len(line.lstrip())]


CP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'
p = (ROOT / CP).read_text(encoding='utf-8')
if 'rhTopBarBlurFixed' in p:
    print('batch63: already applied')
else:
    lines = p.split(NL)

    # 1. import 清单（五查之一）：四个 haze 符号各恰好一次
    required_imports = [
        'import dev.chrisbanes.haze.HazeInput',
        'import dev.chrisbanes.haze.HazeState',
        'import dev.chrisbanes.haze.blur.HazeBlurStyle',
        'import dev.chrisbanes.haze.blur.hazeBlur',
    ]
    for imp in required_imports:
        n = p.count(imp)
        if n != 1:
            fail(CP, 'import count must be exactly one: ' + imp + ' count=' + str(n))

    # 2. TopBar 定义区（更新 #1）：括号范围扫描 + 参数归一化
    def_starts = []
    for i, line in enumerate(lines):
        if line.strip() == 'private fun TopBar(':
            def_starts.append(i)
    if len(def_starts) != 1:
        fail(CP, 'TopBar definition count=' + str(len(def_starts)))
    def_start = def_starts[0]
    def_end = balanced_end(lines, def_start)
    if def_end < 0:
        fail(CP, 'TopBar definition parameter parentheses are unbalanced')

    old_params = lines[def_start + 1:def_end]
    param_indent = '    '
    for line in old_params:
        if line.strip() and not line.strip().startswith('hazeState: HazeState'):
            param_indent = leading_spaces(line)
            break

    removed_def = 0
    clean_params = []
    for line in old_params:
        if line.strip().startswith('hazeState: HazeState'):
            removed_def += 1
        else:
            clean_params.append(line)
    clean_params.insert(0, param_indent + 'hazeState: HazeState,')
    lines = lines[:def_start + 1] + clean_params + lines[def_end:]
    print('batch63: TopBar definition hazeState removed=' + str(removed_def) + ' kept=1')

    # 3. TopBar 调用区（更新 #2）：仅匹配含 settings = setting 的调用
    call_start = -1
    call_end = -1
    for i, line in enumerate(lines):
        if line.strip() != 'TopBar(':
            continue
        end = balanced_end(lines, i)
        if end < 0:
            fail(CP, 'TopBar call parentheses are unbalanced')
        has_settings = any(l2.strip() == 'settings = setting,' for l2 in lines[i + 1:end])
        if has_settings:
            call_start = i
            call_end = end
            break
    if call_start < 0:
        fail(CP, 'TopBar call with settings = setting, not found')

    call_params = lines[call_start + 1:call_end]
    settings_indent = '                    '
    for line in call_params:
        if line.strip() == 'settings = setting,':
            settings_indent = leading_spaces(line)
            break
    removed_call = 0
    clean_call = []
    for line in call_params:
        if line.strip() == 'hazeState = hazeState,':
            removed_call += 1
        else:
            clean_call.append(line)
    clean_call.insert(0, settings_indent + 'hazeState = hazeState,')
    lines = lines[:call_start + 1] + clean_call + lines[call_end:]
    print('batch63: TopBar call hazeState removed=' + str(removed_call) + ' kept=1')

    # 4. API 归一化：alpha05 基础 DSL（Material3 扩展未导入）
    m3 = 0
    for i, line in enumerate(lines):
        if 'HazeBlurStyle.Material3 {' in line:
            lines[i] = line.replace('HazeBlurStyle.Material3 {', 'HazeBlurStyle {')
            m3 += 1
    print('batch63: Material3 DSL replacements=' + str(m3))

    lines = [
        line for line in lines
        if line.strip() != 'import dev.chrisbanes.haze.blur.material3.Material3'
    ]

    # 5. 五查后置复核（作用域 / 括号 / 签名 / 数量 / API 形态）
    text = NL.join(lines)

    d0 = -1
    for i, line in enumerate(lines):
        if line.strip() == 'private fun TopBar(':
            d0 = i
            break
    if d0 < 0:
        fail(CP, 'TopBar definition disappeared after normalization')
    d1 = balanced_end(lines, d0)
    if d1 < 0:
        fail(CP, 'TopBar definition unbalanced after normalization')
    def_text = NL.join(lines[d0:d1 + 1])
    if def_text.count('hazeState: HazeState') != 1:
        fail(CP, 'TopBar definition hazeState count is not one after normalization')

    c0 = -1
    c1 = -1
    for i, line in enumerate(lines):
        if line.strip() != 'TopBar(':
            continue
        end = balanced_end(lines, i)
        if end >= 0 and any(l2.strip() == 'settings = setting,' for l2 in lines[i + 1:end]):
            c0 = i
            c1 = end
            break
    if c0 < 0:
        fail(CP, 'TopBar call disappeared after normalization')
    call_text = NL.join(lines[c0:c1 + 1])
    if call_text.count('hazeState = hazeState,') != 1:
        fail(CP, 'TopBar call hazeState count is not one after normalization')

    state_decl = -1
    for i, line in enumerate(lines):
        if line.strip() == 'val hazeState = rememberHazeState()':
            state_decl = i
            break
    if state_decl < 0 or state_decl > c0:
        fail(CP, 'hazeState declaration missing or after TopBar call (scope check)')

    if 'HazeBlurStyle.Material3 {' in text:
        fail(CP, 'Material3 DSL remains after normalization')
    if 'style = HazeBlurStyle {' not in text:
        fail(CP, 'base HazeBlurStyle DSL missing')
    if 'blurRadius(20.dp)' not in text:
        fail(CP, 'blurRadius DSL body missing')
    if 'Modifier.hazeBlur(' not in text:
        fail(CP, 'hazeBlur modifier missing')
    if 'HazeInput.Sources(hazeState)' not in text:
        fail(CP, 'HazeInput.Sources state wiring missing')

    lines.append('')
    lines.append('// ' + MARK)
    (ROOT / CP).write_text(NL.join(lines), encoding='utf-8')
    print('batch63: five checks passed; TopBar definition/call/API normalized')

print('batch63: OK')
