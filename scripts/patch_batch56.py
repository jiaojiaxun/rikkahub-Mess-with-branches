#!/usr/bin/env python3
'''batch56 v5: 诊断版——锚点不变（已两轮实证正确），加现场 dump + strip 兜底

#164/#165/#166 三连挂同报 "claude rule anchor not found"。
静态验尸已穷尽且矛盾：v4 锚点与仓库文件逐字符一致（MCP 全文证据），
四个前置脚本（chat_ui_tools/local_tool_page/skin_store_init/chat_page_html
及全部 batch 系列）均不碰 ModelContextLengthResolver.kt。

v5 不改锚点逻辑——加三重诊断/兜底：
1. 每步 print 进度（.patch_out.log 尾部可见走到哪步）
2. 匹配失败时 dump 文件里所有含目标 token 的行（::error 带现场）
3. 精确匹配失败 → 逐行 strip 比较 → 行级重组兜底（对空白差异免疫）'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhRegistryTier'


def fail(path, msg):
    print('::error file=' + path + '::batch56 ' + str(msg)[:1400])
    raise SystemExit(1)


def dump_lines_containing(text, needle, label):
    hits = [ln for ln in text.split(NL) if needle in ln]
    if not hits:
        return ' [no line contains ' + needle + ']'
    return ' [' + label + ' lines: ' + ' | '.join(hits[:6])[:900] + ']'


def find_line_index_stripped(lines, target_line):
    want = target_line.strip()
    for i, ln in enumerate(lines):
        if ln.strip() == want:
            return i
    return -1


RS = 'app/src/main/java/me/rerere/rikkahub/data/model/ModelContextLengthResolver.kt'
t = (ROOT / RS).read_text(encoding='utf-8')
print('batch56: file loaded, MARK present = ' + str(MARK in t))
if MARK not in t:
    applied = []

    # ============ 1. import ============
    print('batch56: step1 import...')
    if 'import me.rerere.ai.registry.ModelRegistry' not in t:
        OLD_I = 'import org.json.JSONObject'
        if OLD_I not in t:
            fail(RS, 'import anchor not found' + dump_lines_containing(t, 'org.json', 'import'))
        t = t.replace(OLD_I, 'import me.rerere.ai.registry.ModelRegistry' + NL + OLD_I, 1)
        applied.append('import')
        print('batch56: step1 import OK')
    else:
        applied.append('import(already)')
        print('batch56: step1 import already')

    # ============ 2. resolve 插档 ============
    print('batch56: step2 resolve-tier...')
    OLD_1 = (
        '        // The built-in family table is authoritative for the families it covers. A public' + NL +
        '        // catalog can be stale or expose a route-specific value, so it is only consulted for' + NL +
        '        // models the table does not know.' + NL +
        '        val result = knownContextLength(key) ?: queryPublicCatalog(raw)'
    )
    if 'ModelRegistry.MODEL_CONTEXT_LENGTH.getData(raw)' in t:
        applied.append('resolve-tier(already)')
        print('batch56: step2 resolve-tier already')
    else:
        if OLD_1 not in t:
            fail(RS, 'resolve tier anchor not found' + dump_lines_containing(t, 'knownContextLength(key)', 'resolve'))
        if t.count(OLD_1) != 1:
            fail(RS, 'resolve tier anchor not unique: ' + str(t.count(OLD_1)))
        NEW_1 = (
            '        // ' + MARK + ' (batch56): per-model registry (80 models, fine-grained) beats the' + NL +
            '        // coarse family table - e.g. glm5.1=200K vs glm5.2=1M differ within one family.' + NL +
            '        val registryLength = ModelRegistry.MODEL_CONTEXT_LENGTH.getData(raw)' + NL +
            '        if (registryLength != null && registryLength > 0) {' + NL +
            '            synchronized(cache) { cache[key] = registryLength }' + NL +
            '            return registryLength' + NL +
            '        }' + NL +
            OLD_1
        )
        t = t.replace(OLD_1, NEW_1, 1)
        applied.append('resolve-tier')
        print('batch56: step2 resolve-tier OK')

    # ============ 3. 家族表拆版本（claude/glm/kimi，行级操作） ============
    # 行级策略：splitlines → 按 strip 相等找行号 → 列表重组
    # 对缩进/空白差异免疫（v1-v4 的精确子串匹配对任何空白差异都是零容忍）
    print('batch56: step3 family rules (line-level)...')
    lines = t.split(NL)

    def replace_after_line(lines, needle_line, new_lines, label):
        idx = find_line_index_stripped(lines, needle_line)
        if idx < 0:
            fail(RS, label + ' line not found (stripped)' + dump_lines_containing(NL.join(lines), label.split()[0].lower(), label))
        # 幂等：目标行已是新首行则跳过
        if any(MARK in ln for ln in lines[max(0, idx - 1):idx + 1]):
            print('batch56: ' + label + ' already')
            return lines
        return lines[:idx] + new_lines + lines[idx:]

    # claude：原行 → 4 行新规则 + 原行
    CLAUDE_LINE = '            ContextRule(listOf(' + Q + 'claude' + Q + '), 200_000),'
    CLAUDE_NEW = [
        '            // ' + MARK + ': Claude 4.6+ ships 1M (documented); older Claude stays 200K.',
        '            ContextRule(listOf(' + Q + 'claude' + Q + ', ' + Q + '46' + Q + '), 1_000_000),',
        '            ContextRule(listOf(' + Q + 'claude' + Q + ', ' + Q + '47' + Q + '), 1_000_000),',
        '            ContextRule(listOf(' + Q + 'claude' + Q + ', ' + Q + '48' + Q + '), 1_000_000),',
        '            ContextRule(listOf(' + Q + 'claude' + Q + ', ' + Q + '5' + Q + '), 1_000_000),',
    ]
    lines = replace_after_line(lines, CLAUDE_LINE, CLAUDE_NEW, 'claude')
    print('batch56: step3 claude OK')

    # glm：glm46 行前插 glm47+52+53+5 行（顺序：具体在前）
    GLM_LINE = '            ContextRule(listOf(' + Q + 'glm46' + Q + '), 200_000),'
    GLM_NEW = [
        '            ContextRule(listOf(' + Q + 'glm47' + Q + '), 200_000),',
        '            // ' + MARK + ': GLM 5.2+ ships 1M; 5/5.1 stay 200K (documented).',
        '            ContextRule(listOf(' + Q + 'glm52' + Q + '), 1_000_000),',
        '            ContextRule(listOf(' + Q + 'glm53' + Q + '), 1_000_000),',
        '            ContextRule(listOf(' + Q + 'glm5' + Q + '), 200_000),',
    ]
    lines = replace_after_line(lines, GLM_LINE, GLM_NEW, 'glm')
    print('batch56: step3 glm OK')

    # kimi：kimi 行前插 K3/K2.6/K2.5 行，且原行值改为 131_072
    KIMI_LINE = '            ContextRule(listOf(' + Q + 'kimi' + Q + '), 262_144),'
    KIMI_NEW = [
        '            // ' + MARK + ': Kimi K3=1M, K2.5/K2.6=256K, plain K2=128K (documented).',
        '            ContextRule(listOf(' + Q + 'kimik3' + Q + '), 1_000_000),',
        '            ContextRule(listOf(' + Q + 'kimik26' + Q + '), 262_144),',
        '            ContextRule(listOf(' + Q + 'kimik25' + Q + '), 262_144),',
    ]
    idx = find_line_index_stripped(lines, KIMI_LINE)
    if idx < 0:
        fail(RS, 'kimi line not found (stripped)' + dump_lines_containing(NL.join(lines), 'kimi', 'kimi'))
    if not any(MARK in ln for ln in lines[max(0, idx - 1):idx + 1]):
        lines = lines[:idx] + KIMI_NEW + [
            '            ContextRule(listOf(' + Q + 'kimi' + Q + '), 131_072),',
        ] + lines[idx + 1:]
        print('batch56: step3 kimi OK')
    else:
        print('batch56: step3 kimi already')

    t = NL.join(lines)

    # ============ 自检 ============
    print('batch56: step4 selfcheck...')
    for need in ['import me.rerere.ai.registry.ModelRegistry',
                 'ModelRegistry.MODEL_CONTEXT_LENGTH.getData(raw)',
                 'ContextRule(listOf(' + Q + 'kimik3' + Q + '), 1_000_000)',
                 'ContextRule(listOf(' + Q + 'glm52' + Q + '), 1_000_000)',
                 'ContextRule(listOf(' + Q + 'claude' + Q + ', ' + Q + '46' + Q + '), 1_000_000)']:
        if need not in t:
            fail(RS, 'selfcheck missing: ' + need)
    (ROOT / RS).write_text(t, encoding='utf-8')
    print('batch56: applied = ' + ', '.join(applied))
else:
    print('batch56: already applied')

print('batch56 v5: OK')
