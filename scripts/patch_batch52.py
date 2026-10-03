#!/usr/bin/env python3
'''batch52 v3: 模型上下文长度库（第三人视角审查后的修复版）

#155 死因：o 系列锚点 tokens(tokenRegex("^o$"), tokenRegex("^\d+$"))
在 Python 源里反斜杠转义不匹配 → fail（铁律5「零反斜杠」违反）。
v3 策略：放弃 tokens 行锚点，改用块名锚点 NAME = defineModel { → 向后找
块尾 NL+4空格'}', 插入 contextLength(N)。块名无引号无反斜杠，天然免疫。

审查中发现的数值修正（对照《全球主流模型上下文长度.md》v3）：
- GLM_5_1: 200_000（v2 误写 1M；文档明确 5.1=200K，5.2 才是 1M）
- STEP_3_7_FLASH: 128_000（文档「128K–256K 平台为准」，保守取下限）
- HY3/HY4: 移除（文档明确「未公开」，不编数值——缺失优于错误）
本轮共 80 个模型灌数。

ModelDsl 部分（D1-D4）在 #155 已验证 OK，逐字保留。
'''
from pathlib import Path

ROOT = Path.cwd()
DSL = 'ai/src/main/java/me/rerere/ai/registry/ModelDsl.kt'
REG = 'ai/src/main/java/me/rerere/ai/registry/ModelRegistry.kt'
NL = chr(10)
MARK_DSL = 'rhCtxDsl'
MARK_REG = 'rhCtxRegistry'


def fail(path, msg):
    print('::error file=' + path + '::batch52 ' + str(msg)[:1500])
    raise SystemExit(1)


# ============================================================
# 1. ModelDsl.kt — 恢复 contextLength DSL（#155 实证 OK，原样保留）
# ============================================================
d = (ROOT / DSL).read_text(encoding='utf-8')
if MARK_DSL not in d:
    OLD_D1 = (
        'class ModelDefinition(' + NL +
        '    private val matcher: TokenMatcher,' + NL +
        '    val inputModalities: Set<Modality>,' + NL +
        '    val outputModalities: Set<Modality>,' + NL +
        '    val abilities: Set<ModelAbility>' + NL +
        ') : ModelSelector {'
    )
    NEW_D1 = (
        'class ModelDefinition(' + NL +
        '    private val matcher: TokenMatcher,' + NL +
        '    val inputModalities: Set<Modality>,' + NL +
        '    val outputModalities: Set<Modality>,' + NL +
        '    val abilities: Set<ModelAbility>,' + NL +
        '    // ' + MARK_DSL + ' (batch52): 上下文窗口（tokens），来自《全球主流模型上下文长度》官方口径' + NL +
        '    val contextLength: Int? = null' + NL +
        ') : ModelSelector {'
    )
    if OLD_D1 not in d:
        fail(DSL, 'D1 ModelDefinition anchor not found')
    d = d.replace(OLD_D1, NEW_D1, 1)

    OLD_D2 = (
        'class ModelDefinitionBuilder {' + NL +
        '    private val matchers = mutableListOf<TokenMatcher>()' + NL +
        '    private val inputModalities = mutableSetOf(Modality.TEXT)' + NL +
        '    private val outputModalities = mutableSetOf(Modality.TEXT)' + NL +
        '    private val abilities = mutableSetOf<ModelAbility>()' + NL + NL +
        '    fun tokens(vararg specs: String) {'
    )
    NEW_D2 = (
        'class ModelDefinitionBuilder {' + NL +
        '    private val matchers = mutableListOf<TokenMatcher>()' + NL +
        '    private val inputModalities = mutableSetOf(Modality.TEXT)' + NL +
        '    private val outputModalities = mutableSetOf(Modality.TEXT)' + NL +
        '    private val abilities = mutableSetOf<ModelAbility>()' + NL +
        '    private var contextLength: Int? = null // ' + MARK_DSL + NL + NL +
        '    fun tokens(vararg specs: String) {'
    )
    if OLD_D2 not in d:
        fail(DSL, 'D2 builder fields anchor not found')
    d = d.replace(OLD_D2, NEW_D2, 1)

    OLD_D3 = (
        '    fun ability(vararg abilities: ModelAbility) {' + NL +
        '        this.abilities.addAll(abilities)' + NL +
        '    }' + NL + NL +
        '    fun build(): ModelDefinition {'
    )
    NEW_D3 = (
        '    fun ability(vararg abilities: ModelAbility) {' + NL +
        '        this.abilities.addAll(abilities)' + NL +
        '    }' + NL + NL +
        '    // ' + MARK_DSL + ' (batch52): 注册表内声明上下文长度（tokens）' + NL +
        '    fun contextLength(tokens: Int) {' + NL +
        '        contextLength = tokens' + NL +
        '    }' + NL + NL +
        '    fun build(): ModelDefinition {'
    )
    if OLD_D3 not in d:
        fail(DSL, 'D3 ability anchor not found')
    d = d.replace(OLD_D3, NEW_D3, 1)

    OLD_D4 = (
        '        return ModelDefinition(' + NL +
        '            matcher = matcher,' + NL +
        '            inputModalities = inputModalities.toSet(),' + NL +
        '            outputModalities = outputModalities.toSet(),' + NL +
        '            abilities = abilities.toSet()' + NL +
        '        )'
    )
    NEW_D4 = (
        '        return ModelDefinition(' + NL +
        '            matcher = matcher,' + NL +
        '            inputModalities = inputModalities.toSet(),' + NL +
        '            outputModalities = outputModalities.toSet(),' + NL +
        '            abilities = abilities.toSet(),' + NL +
        '            contextLength = contextLength' + NL +
        '        )'
    )
    if OLD_D4 not in d:
        fail(DSL, 'D4 build anchor not found')
    d = d.replace(OLD_D4, NEW_D4, 1)

    for need in [MARK_DSL, 'fun contextLength(tokens: Int)', 'contextLength = contextLength']:
        if need not in d:
            fail(DSL, 'DSL selfcheck missing: ' + need)
    (ROOT / DSL).write_text(d, encoding='utf-8')
    print('batch52: ModelDsl OK')
else:
    print('batch52: ModelDsl already applied')

# ============================================================
# 2. ModelRegistry.kt — 查询入口 + 块名锚点灌数
# ============================================================
r = (ROOT / REG).read_text(encoding='utf-8')
if MARK_REG not in r:
    OLD_R0 = (
        '    val MODEL_ABILITIES = ModelData { modelId ->' + NL +
        '        val abilities = resolveModels(modelId)' + NL +
        '            .flatMap { it.abilities }' + NL +
        '            .toSet()' + NL +
        '        buildList {' + NL +
        '            if (ModelAbility.TOOL in abilities) add(ModelAbility.TOOL)' + NL +
        '            if (ModelAbility.REASONING in abilities) add(ModelAbility.REASONING)' + NL +
        '        }' + NL +
        '    }'
    )
    NEW_R0 = (
        '    val MODEL_ABILITIES = ModelData { modelId ->' + NL +
        '        val abilities = resolveModels(modelId)' + NL +
        '            .flatMap { it.abilities }' + NL +
        '            .toSet()' + NL +
        '        buildList {' + NL +
        '            if (ModelAbility.TOOL in abilities) add(ModelAbility.TOOL)' + NL +
        '            if (ModelAbility.REASONING in abilities) add(ModelAbility.REASONING)' + NL +
        '        }' + NL +
        '    }' + NL + NL +
        '    // ' + MARK_REG + ' (batch52): 按注册表解析上下文长度；多模型命中时取最大值。' + NL +
        '    // 调用方优先级：OpenRouter/平台实测 model.contextLength > 本注册表默认。' + NL +
        '    val MODEL_CONTEXT_LENGTH = ModelData { modelId ->' + NL +
        '        resolveModels(modelId).mapNotNull { it.contextLength }.maxOrNull()' + NL +
        '    }'
    )
    if OLD_R0 not in r:
        fail(REG, 'R0 MODEL_ABILITIES anchor not found')
    r = r.replace(OLD_R0, NEW_R0, 1)

    # --- 块名锚点灌数（80 模型，数值=文档 v3 官方口径） ---
    VALUES = [
        ('GPT4O', 128000),
        ('GPT_4_1', 1047576),
        ('OPENAI_O_MODELS', 200000),
        ('GPT_OSS', 131072),
        ('GPT_5', 400000),
        ('GPT_5_1', 400000),
        ('GPT_5_2', 400000),
        ('GPT_5_3', 400000),
        ('GPT_5_4', 400000),
        ('GPT_5_4_MINI', 400000),
        ('GPT_5_4_NANO', 400000),
        ('GPT_5_5', 1048576),
        ('GPT_5_6', 1048576),
        ('GPT_6', 1048576),
        ('GEMINI_20_FLASH', 1048576),
        ('GEMINI_2_5_FLASH', 1048576),
        ('GEMINI_2_5_PRO', 1048576),
        ('GEMINI_3_PRO', 1048576),
        ('GEMINI_3_FLASH', 1048576),
        ('GEMINI_3_1_PRO_PREVIEW', 1048576),
        ('GEMINI_3_1_PRO_PREVIEW_CUSTOMTOOLS', 1048576),
        ('GEMINI_3_5', 1048576),
        ('GEMINI_FLASH_LATEST', 1048576),
        ('GEMINI_PRO_LATEST', 1048576),
        ('CLAUDE_SONNET_3_5', 200000),
        ('CLAUDE_SONNET_3_7', 200000),
        ('CLAUDE_4', 200000),
        ('CLAUDE_4_5', 200000),
        ('CLAUDE_SONNET_4_6', 1000000),
        ('CLAUDE_OPUS_4_6', 1000000),
        ('CLAUDE_OPUS_4_7', 1000000),
        ('CLAUDE_OPUS_4_8', 1000000),
        ('CLAUDE_SONNET_5', 1000000),
        ('CLAUDE_OPUS_5', 1000000),
        ('DEEPSEEK_V3_MODEL', 128000),
        ('DEEPSEEK_CHAT', 1000000),
        ('DEEPSEEK_R1_MODEL', 128000),
        ('DEEPSEEK_REASONER', 1000000),
        ('DEEPSEEK_V4_FLASH', 1000000),
        ('DEEPSEEK_V4_FLASH_VISION_EXP', 1000000),
        ('DEEPSEEK_V4_PRO', 1000000),
        ('DEEPSEEK_FLASH', 1000000),
        ('DEEPSEEK_V4_1_FLASH', 1000000),
        ('DEEPSEEK_V3_1', 128000),
        ('DEEPSEEK_V3_2', 128000),
        ('QWEN_3', 128000),
        ('QWEN_3_5', 1000000),
        ('QWEN_3_6', 1000000),
        ('QWEN_3_7', 1000000),
        ('QWEN_3_8', 1000000),
        ('QWEN_3_5_MAX', 1000000),
        ('QWEN_3_6_MAX', 1000000),
        ('QWEN_3_7_MAX', 1000000),
        ('QWEN_3_8_MAX', 1000000),
        ('DOUBAO_1_6', 256000),
        ('DOUBAO_1_8', 256000),
        ('DOUBAO_2_0', 256000),
        ('DOUBAO_2_1', 256000),
        ('GROK_4', 256000),
        ('KIMI_K2', 128000),
        ('KIMI_K2_5', 256000),
        ('KIMI_K2_6', 256000),
        ('KIMI_K3', 1000000),
        ('KIMI_K3_ALIAS', 1000000),
        ('STEP_3', 128000),
        ('STEP_3_7_FLASH', 128000),
        ('STEP_5', 1000000),
        ('GLM_4_5', 128000),
        ('GLM_4_6', 200000),
        ('GLM_4_7', 200000),
        ('GLM_5', 200000),
        ('GLM_5_1', 200000),
        ('GLM_5_2', 1000000),
        ('GLM_5_3', 1000000),
        ('GLM_5_3_FLASH', 1000000),
        ('MINIMAX_M2', 204800),
        ('MINIMAX_M2_5', 204800),
        ('MINIMAX_M2_7', 204800),
        ('MINIMAX_M3', 1000000),
        ('XIAOMI_MIMO_V2_6', 208000),
    ]

    applied = 0
    for name, value in VALUES:
        header = name + ' = defineModel {'
        if r.count(header) != 1:
            fail(REG, 'header count != 1 for ' + name + ' (found ' + str(r.count(header)) + ')')
        pos = r.find(header)
        end = r.find(NL + '    }', pos)
        if end < 0:
            fail(REG, 'block end not found for ' + name)
        r = r[:end] + NL + '        contextLength(' + str(value) + ')' + r[end:]
        applied += 1

    if applied != len(VALUES):
        fail(REG, 'applied mismatch: ' + str(applied) + ' != ' + str(len(VALUES)))
    if r.count('contextLength(') != len(VALUES):
        fail(REG, 'selfcheck: contextLength call count = ' + str(r.count('contextLength(')))
    if 'MODEL_CONTEXT_LENGTH' not in r:
        fail(REG, 'selfcheck: MODEL_CONTEXT_LENGTH missing')

    (ROOT / REG).write_text(r, encoding='utf-8')
    print('batch52: ModelRegistry OK (' + str(applied) + ' models infused)')
else:
    print('batch52: ModelRegistry already applied')

print('batch52 v3: OK')
