#!/usr/bin/env python3
'''batch56 v3: 修 #164 真根因——Python 字符串里的反斜杠转义陷阱（铁律5 第四犯）

#164 死因链（完整验尸）：
- annotations: `claude rule anchor not found`
- v1 的 OLD_2 = '    ContextRule(listOf(\"claude\"), 200_000),'
  ——写在单引号字符串里，`\"` 在 Python 里= 反斜杠+引号 两个字符
  ——而目标文件里是纯引号（无反斜杠）→ 永远 not found
- 铁律5「零反斜杠」第四犯：#96-108(f-string)、#155(锚点反斜杠)、
  #160前(裸跨行)、#164(单引号串内转义引号)

v3 根治：所有含双引号的锚点/产物字符串一律用 chr(34)（Q）构造，
物理杜绝任何反斜杠进入 Python 源码。'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)  # 双引号
MARK = 'rhRegistryTier'


def fail(path, msg):
    print('::error file=' + path + '::batch56 ' + str(msg)[:1500])
    raise SystemExit(1)


def cr(tokens, value):
    # 生成一行 ContextRule：12空格 + ContextRule(listOf("t1","t2"), N),
    return '            ContextRule(listOf(' + Q + tokens.join(Q + ', ' + Q) + Q + '), ' + str(value) + '),'


RS = 'app/src/main/java/me/rerere/rikkahub/data/model/ModelContextLengthResolver.kt'
t = (ROOT / RS).read_text(encoding='utf-8')
if MARK not in t:
    applied = []

    # 1. import
    if 'import me.rerere.ai.registry.ModelRegistry' not in t:
        OLD_I = 'import org.json.JSONObject'
        if OLD_I not in t:
            fail(RS, 'import anchor not found')
        t = t.replace(OLD_I, 'import me.rerere.ai.registry.ModelRegistry' + NL + OLD_I, 1)
        applied.append('import')

    # 2. resolve 插档
    OLD_1 = (
        '        // The built-in family table is authoritative for the families it covers. A public' + NL +
        '        // catalog can be stale or expose a route-specific value, so it is only consulted for' + NL +
        '        // models the table does not know.' + NL +
        '        val result = knownContextLength(key) ?: queryPublicCatalog(raw)'
    )
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
    if 'ModelRegistry.MODEL_CONTEXT_LENGTH.getData(raw)' in t:
        applied.append('resolve-tier(already)')
    elif OLD_1 in t:
        if t.count(OLD_1) != 1:
            fail(RS, 'resolve tier anchor not unique')
        t = t.replace(OLD_1, NEW_1, 1)
        applied.append('resolve-tier')
    else:
        fail(RS, 'resolve tier anchor not found')

    # 3a. claude 拆版本
    OLD_CLAUDE = cr('claude', '200_000')
    if 'ContextRule(listOf(' + Q + 'claude' + Q + ', ' + Q + '46' + Q + '), 1_000_000)' in t:
        applied.append('claude(already)')
    elif OLD_CLAUDE in t:
        if t.count(OLD_CLAUDE) != 1:
            fail(RS, 'claude anchor not unique: ' + str(t.count(OLD_CLAUDE)))
        NEW_CLAUDE = (
            '            // ' + MARK + ': Claude 4.6+ ships 1M (documented); older Claude stays 200K.' + NL +
            cr('claude,46', '1_000_000') + NL +
            cr('claude,47', '1_000_000') + NL +
            cr('claude,48', '1_000_000') + NL +
            cr('claude,5', '1_000_000') + NL +
            OLD_CLAUDE
        )
        t = t.replace(OLD_CLAUDE, NEW_CLAUDE, 1)
        applied.append('claude')
    else:
        fail(RS, 'claude rule anchor not found')

    # 3b. glm 拆版本（锚=glm46 行起的五行块）
    OLD_GLM = (
        cr('glm46', '200_000') + NL +
        cr('glm45', '128_000') + NL +
        cr('glm4', '128_000') + NL +
        cr('chatglm', '128_000') + NL +
        cr('glm', '128_000')
    )
    if 'ContextRule(listOf(' + Q + 'glm52' + Q + '), 1_000_000)' in t:
        applied.append('glm(already)')
    elif OLD_GLM in t:
        NEW_GLM = (
            cr('glm46', '200_000') + NL +
            cr('glm47', '200_000') + NL +
            '            // ' + MARK + ': GLM 5.2+ ships 1M; 5/5.1 stay 200K (documented).' + NL +
            cr('glm52', '1_000_000') + NL +
            cr('glm53', '1_000_000') + NL +
            cr('glm5', '200_000') + NL +
            cr('glm45', '128_000') + NL +
            cr('glm4', '128_000') + NL +
            cr('chatglm', '128_000') + NL +
            cr('glm', '128_000')
        )
        t = t.replace(OLD_GLM, NEW_GLM, 1)
        applied.append('glm')
    else:
        fail(RS, 'glm rules anchor not found')

    # 3c. kimi 拆版本
    OLD_KIMI = (
        cr('kimi', '262_144') + NL +
        cr('moonshot', '131_072')
    )
    if 'ContextRule(listOf(' + Q + 'kimik3' + Q + '), 1_000_000)' in t:
        applied.append('kimi(already)')
    elif OLD_KIMI in t:
        NEW_KIMI = (
            '            // ' + MARK + ': Kimi K3=1M, K2.5/K2.6=256K, plain K2=128K (documented).' + NL +
            cr('kimik3', '1_000_000') + NL +
            cr('kimik26', '262_144') + NL +
            cr('kimik25', '262_144') + NL +
            cr('kimi', '131_072') + NL +
            cr('moonshot', '131_072')
        )
        t = t.replace(OLD_KIMI, NEW_KIMI, 1)
        applied.append('kimi')
    else:
        fail(RS, 'kimi rule anchor not found')

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

print('batch56 v3: OK')
