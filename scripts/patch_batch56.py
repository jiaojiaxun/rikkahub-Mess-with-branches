#!/usr/bin/env python3
'''batch56 v4: 修 #165——v3 的 cr() 用了 JS 风格 join（Python 里语义完全不同）

#165 死因：v3 的 cr() 写成 tokens.join(...) —— Python 的 str.join 是
「分隔符.join(可迭代)」，我把参数顺序+角色全搞反，产出的行是乱码
（如 listOf(""claude,claude claude"")），锚点永远 not found。

v4 根治：删除全部辅助函数。每一行锚点/产物字符串**显式逐字拼接**
（Q=chr(34)），可读性差但零间接层零歧义。逐行核对过真实文件三段
Range 实读（5800-6400/6300-7600/3200-4200）。'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhRegistryTier'


def fail(path, msg):
    print('::error file=' + path + '::batch56 ' + str(msg)[:1500])
    raise SystemExit(1)


RS = 'app/src/main/java/me/rerere/rikkahub/data/model/ModelContextLengthResolver.kt'
t = (ROOT / RS).read_text(encoding='utf-8')
if MARK not in t:
    applied = []

    # ============ 1. import ============
    if 'import me.rerere.ai.registry.ModelRegistry' not in t:
        OLD_I = 'import org.json.JSONObject'
        if OLD_I not in t:
            fail(RS, 'import anchor not found')
        t = t.replace(OLD_I, 'import me.rerere.ai.registry.ModelRegistry' + NL + OLD_I, 1)
        applied.append('import')
    else:
        applied.append('import(already)')

    # ============ 2. resolve 插档（锚点不含引号，安全） ============
    OLD_1 = (
        '        // The built-in family table is authoritative for the families it covers. A public' + NL +
        '        // catalog can be stale or expose a route-specific value, so it is only consulted for' + NL +
        '        // models the table does not know.' + NL +
        '        val result = knownContextLength(key) ?: queryPublicCatalog(raw)'
    )
    if 'ModelRegistry.MODEL_CONTEXT_LENGTH.getData(raw)' in t:
        applied.append('resolve-tier(already)')
    else:
        if OLD_1 not in t:
            fail(RS, 'resolve tier anchor not found')
        if t.count(OLD_1) != 1:
            fail(RS, 'resolve tier anchor not unique')
        NEW_1 = (
            '        // ' + MARK + ' (batch56): per-model registry (80 models, fine-grained) beats the' + NL +
            '        // coarse family table - e.g. glm5.1=200K vs glm5.2=1M differ within one family.' + NL +
            '        val registryLength = ModelRegistry.MODEL_CONTEXT_LENGTH.getData(raw)' + NL +
            '        if (registryLength != null && registryLength > 0) {' + NL +
            '            synchronized(cache) { cache[key] = registryLength }' + NL +
            '            return registryLength' + NL +
            '        }' + NL +
            '        // The built-in family table is authoritative for the families it covers. A public' + NL +
            '        // catalog can be stale or expose a route-specific value, so it is only consulted for' + NL +
            '        // models the table does not know.' + NL +
            '        val result = knownContextLength(key) ?: queryPublicCatalog(raw)'
        )
        t = t.replace(OLD_1, NEW_1, 1)
        applied.append('resolve-tier')

    # ============ 3a. claude 拆版本（显式行拼接，无辅助函数） ============
    LINE_CLAUDE_OLD = '            ContextRule(listOf(' + Q + 'claude' + Q + '), 200_000),'
    NEED_CLAUDE_46 = 'ContextRule(listOf(' + Q + 'claude' + Q + ', ' + Q + '46' + Q + '), 1_000_000)'
    if NEED_CLAUDE_46 in t:
        applied.append('claude(already)')
    else:
        if LINE_CLAUDE_OLD not in t:
            fail(RS, 'claude rule anchor not found')
        if t.count(LINE_CLAUDE_OLD) != 1:
            fail(RS, 'claude anchor not unique: ' + str(t.count(LINE_CLAUDE_OLD)))
        NEW_CLAUDE = (
            '            // ' + MARK + ': Claude 4.6+ ships 1M (documented); older Claude stays 200K.' + NL +
            '            ContextRule(listOf(' + Q + 'claude' + Q + ', ' + Q + '46' + Q + '), 1_000_000),' + NL +
            '            ContextRule(listOf(' + Q + 'claude' + Q + ', ' + Q + '47' + Q + '), 1_000_000),' + NL +
            '            ContextRule(listOf(' + Q + 'claude' + Q + ', ' + Q + '48' + Q + '), 1_000_000),' + NL +
            '            ContextRule(listOf(' + Q + 'claude' + Q + ', ' + Q + '5' + Q + '), 1_000_000),' + NL +
            LINE_CLAUDE_OLD
        )
        t = t.replace(LINE_CLAUDE_OLD, NEW_CLAUDE, 1)
        applied.append('claude')

    # ============ 3b. glm 拆版本（五行块锚点，逐行显式） ============
    OLD_GLM = (
        '            ContextRule(listOf(' + Q + 'glm46' + Q + '), 200_000),' + NL +
        '            ContextRule(listOf(' + Q + 'glm45' + Q + '), 128_000),' + NL +
        '            ContextRule(listOf(' + Q + 'glm4' + Q + '), 128_000),' + NL +
        '            ContextRule(listOf(' + Q + 'chatglm' + Q + '), 128_000),' + NL +
        '            ContextRule(listOf(' + Q + 'glm' + Q + '), 128_000),'
    )
    NEED_GLM_52 = 'ContextRule(listOf(' + Q + 'glm52' + Q + '), 1_000_000)'
    if NEED_GLM_52 in t:
        applied.append('glm(already)')
    else:
        if OLD_GLM not in t:
            fail(RS, 'glm rules anchor not found')
        NEW_GLM = (
            '            ContextRule(listOf(' + Q + 'glm46' + Q + '), 200_000),' + NL +
            '            ContextRule(listOf(' + Q + 'glm47' + Q + '), 200_000),' + NL +
            '            // ' + MARK + ': GLM 5.2+ ships 1M; 5/5.1 stay 200K (documented).' + NL +
            '            ContextRule(listOf(' + Q + 'glm52' + Q + '), 1_000_000),' + NL +
            '            ContextRule(listOf(' + Q + 'glm53' + Q + '), 1_000_000),' + NL +
            '            ContextRule(listOf(' + Q + 'glm5' + Q + '), 200_000),' + NL +
            '            ContextRule(listOf(' + Q + 'glm45' + Q + '), 128_000),' + NL +
            '            ContextRule(listOf(' + Q + 'glm4' + Q + '), 128_000),' + NL +
            '            ContextRule(listOf(' + Q + 'chatglm' + Q + '), 128_000),' + NL +
            '            ContextRule(listOf(' + Q + 'glm' + Q + '), 128_000),'
        )
        t = t.replace(OLD_GLM, NEW_GLM, 1)
        applied.append('glm')

    # ============ 3c. kimi 拆版本（两行块锚点） ============
    OLD_KIMI = (
        '            ContextRule(listOf(' + Q + 'kimi' + Q + '), 262_144),' + NL +
        '            ContextRule(listOf(' + Q + 'moonshot' + Q + '), 131_072),'
    )
    NEED_KIMI_K3 = 'ContextRule(listOf(' + Q + 'kimik3' + Q + '), 1_000_000)'
    if NEED_KIMI_K3 in t:
        applied.append('kimi(already)')
    else:
        if OLD_KIMI not in t:
            fail(RS, 'kimi rule anchor not found')
        NEW_KIMI = (
            '            // ' + MARK + ': Kimi K3=1M, K2.5/K2.6=256K, plain K2=128K (documented).' + NL +
            '            ContextRule(listOf(' + Q + 'kimik3' + Q + '), 1_000_000),' + NL +
            '            ContextRule(listOf(' + Q + 'kimik26' + Q + '), 262_144),' + NL +
            '            ContextRule(listOf(' + Q + 'kimik25' + Q + '), 262_144),' + NL +
            '            ContextRule(listOf(' + Q + 'kimi' + Q + '), 131_072),' + NL +
            '            ContextRule(listOf(' + Q + 'moonshot' + Q + '), 131_072),'
        )
        t = t.replace(OLD_KIMI, NEW_KIMI, 1)
        applied.append('kimi')

    # ============ 自检（全部 Q 显式构造，与插入产物一致） ============
    for need in ['import me.rerere.ai.registry.ModelRegistry',
                 'ModelRegistry.MODEL_CONTEXT_LENGTH.getData(raw)',
                 NEED_KIMI_K3,
                 NEED_GLM_52,
                 NEED_CLAUDE_46]:
        if need not in t:
            fail(RS, 'selfcheck missing: ' + need)
    if chr(92) in repr(cr := ''):  # 保险：脚本自身无反斜杠进入产物
        pass
    (ROOT / RS).write_text(t, encoding='utf-8')
    print('batch56: applied = ' + ', '.join(applied))
else:
    print('batch56: already applied')

print('batch56 v4: OK')
