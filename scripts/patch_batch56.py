#!/usr/bin/env python3
'''batch56: 上下文解析链插档——注册表(80模型)优先于家族表 + 家族表过时值修正

审计修正（2026-10-03 22:50）：
- 接线已存在（ModelContextLengthResolver，NerdLine/压缩阈值都走它）
- 但 batch52 的 80 模型注册表没人读——与 Resolver 的 CONTEXT_RULES 家族表并行
- 家族表过时：kimi 全家 262_144（实际 K2=128K/K3=1M）、glm 全家 128_000
  （5.1=200K/5.2+=1M）、claude 全家 200_000（4.6+=1M）

改动：
1. ModelContextLengthResolver.resolve() 的 knownContextLength 前插注册表查询
   ——三级链变四级：provider 元数据 > 注册表 > 家族表 > 公共目录
2. 家族表修正三处（kimi 拆版本/glm 拆版本/claude 拆版本——上下顺序敏感，
   specific 在 general 之前）

锚点：Resolver 全文已实读（2026-10-03 22:50）。原始形态无人碰。'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhRegistryTier'


def fail(path, msg):
    print('::error file=' + path + '::batch56 ' + str(msg)[:1500])
    raise SystemExit(1)


RS = 'app/src/main/java/me/rerere/rikkahub/data/model/ModelContextLengthResolver.kt'
t = (ROOT / RS).read_text(encoding='utf-8')
if MARK not in t:
    # 1. import 区加 ModelRegistry（anchor: 已有 import org.json.JSONObject）
    OLD_I = 'import org.json.JSONObject'
    NEW_I = ('import me.rerere.ai.registry.ModelRegistry' + NL + 'import org.json.JSONObject')
    if OLD_I not in t:
        fail(RS, 'import anchor not found')
    t = t.replace(OLD_I, NEW_I, 1)

    # 2. resolve() 插档：knownContextLength 前查注册表
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
    if OLD_1 not in t:
        fail(RS, 'resolve tier anchor not found')
    if t.count(OLD_1) != 1:
        fail(RS, 'resolve tier anchor not unique')
    t = t.replace(OLD_1, NEW_1, 1)

    # 3. 家族表过时值修正（顺序敏感：specific 在 general 前）
    # 3a. claude 拆版本：4.6+ = 1M，其余 200K
    OLD_2 = '            ContextRule(listOf("claude"), 200_000),'
    NEW_2 = (
        '            // ' + MARK + ': Claude 4.6+ ships 1M (documented); older Claude stays 200K.' + NL +
        '            ContextRule(listOf("claude", "46"), 1_000_000),' + NL +
        '            ContextRule(listOf("claude", "47"), 1_000_000),' + NL +
        '            ContextRule(listOf("claude", "48"), 1_000_000),' + NL +
        '            ContextRule(listOf("claude", "5"), 1_000_000),' + NL +
        '            ContextRule(listOf("claude"), 200_000),'
    )
    if OLD_2 not in t:
        fail(RS, 'claude rule anchor not found')
    t = t.replace(OLD_2, NEW_2, 1)

    # 3b. glm 拆版本：5.2+ = 1M，5/5.1 = 200K，4.6/4.7 = 200K，4.5 = 128K
    OLD_3 = (
        '            ContextRule(listOf("glm46"), 200_000),' + NL +
        '            ContextRule(listOf("glm45"), 128_000),' + NL +
        '            ContextRule(listOf("glm4"), 128_000),' + NL +
        '            ContextRule(listOf("chatglm"), 128_000),' + NL +
        '            ContextRule(listOf("glm"), 128_000),'
    )
    NEW_3 = (
        '            ContextRule(listOf("glm46"), 200_000),' + NL +
        '            ContextRule(listOf("glm47"), 200_000),' + NL +
        '            // ' + MARK + ': GLM 5.2+ ships 1M; 5/5.1 stay 200K (documented).' + NL +
        '            ContextRule(listOf("glm52"), 1_000_000),' + NL +
        '            ContextRule(listOf("glm53"), 1_000_000),' + NL +
        '            ContextRule(listOf("glm5"), 200_000),' + NL +
        '            ContextRule(listOf("glm45"), 128_000),' + NL +
        '            ContextRule(listOf("glm4"), 128_000),' + NL +
        '            ContextRule(listOf("chatglm"), 128_000),' + NL +
        '            ContextRule(listOf("glm"), 128_000),'
    )
    if OLD_3 not in t:
        fail(RS, 'glm rules anchor not found')
    t = t.replace(OLD_3, NEW_3, 1)

    # 3c. kimi 拆版本：K3 = 1M，K2.5+ = 256K，K2 旧版 = 128K
    OLD_4 = (
        '            ContextRule(listOf("kimi"), 262_144),' + NL +
        '            ContextRule(listOf("moonshot"), 131_072),'
    )
    NEW_4 = (
        '            // ' + MARK + ': Kimi K3=1M, K2.5/K2.6=256K, plain K2=128K (documented).' + NL +
        '            ContextRule(listOf("kimik3"), 1_000_000),' + NL +
        '            ContextRule(listOf("kimik26"), 262_144),' + NL +
        '            ContextRule(listOf("kimik25"), 262_144),' + NL +
        '            ContextRule(listOf("kimi"), 131_072),' + NL +
        '            ContextRule(listOf("moonshot"), 131_072),'
    )
    if OLD_4 not in t:
        fail(RS, 'kimi rule anchor not found')
    t = t.replace(OLD_4, NEW_4, 1)

    for need in [MARK, 'ModelRegistry.MODEL_CONTEXT_LENGTH.getData(raw)',
                 'ContextRule(listOf("kimik3"), 1_000_000)',
                 'ContextRule(listOf("glm52"), 1_000_000)',
                 'ContextRule(listOf("claude", "46"), 1_000_000)']:
        if need not in t:
            fail(RS, 'selfcheck missing: ' + need)
    (ROOT / RS).write_text(t, encoding='utf-8')
    print('batch56: Resolver OK')
else:
    print('batch56: already applied')

print('batch56: OK')
