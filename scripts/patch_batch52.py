#!/usr/bin/env python3
'''batch52 v2: 修 v1 的 doubao-2.1 锚点笔误（visionImport→visionInput），
并对其余锚点做了全文核对。其余与 v1 一致。'''
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
# 1. ModelDsl.kt — 恢复 contextLength（上游 2.5.5 实现恢复）
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
# 2. ModelRegistry.kt — 查询入口 + 全量灌数
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

    # --- 全量灌数。锚点 = 各模型 builder 块逐字节（真实读取）。 ---
    INFUSIONS = [
        ('        tokens("gpt", "4", "o")' + NL + '        visionInput()' + NL + '        toolAbility()' + NL + '    }',
         '        tokens("gpt", "4", "o")' + NL + '        visionInput()' + NL + '        toolAbility()' + NL + '        contextLength(128_000)' + NL + '    }'),
        ('        tokens("gpt", "4", "1")' + NL + '        visionInput()' + NL + '        toolAbility()' + NL + '    }',
         '        tokens("gpt", "4", "1")' + NL + '        visionInput()' + NL + '        toolAbility()' + NL + '        contextLength(1_047_576)' + NL + '    }'),
        ('        tokens(tokenRegex("^o$"), tokenRegex("^\\d+$"))' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens(tokenRegex("^o$"), tokenRegex("^\\d+$"))' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(200_000)' + NL + '    }'),
        ('        tokens("gpt", "oss")' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("gpt", "oss")' + NL + '        toolReasoningAbility()' + NL + '        contextLength(131_072)' + NL + '    }'),
        ('        tokens("gpt", "5")' + NL + '        notTokens("gpt", "5", ".")' + NL + '        notTokens("gpt", "5", "chat")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("gpt", "5")' + NL + '        notTokens("gpt", "5", ".")' + NL + '        notTokens("gpt", "5", "chat")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(400_000)' + NL + '    }'),
        ('        tokens("gpt", "5", "1")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("gpt", "5", "1")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(400_000)' + NL + '    }'),
        ('        tokens("gpt", "5", "2")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("gpt", "5", "2")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(400_000)' + NL + '    }'),
        ('        tokens("gpt", "5", "3")' + NL + '        visionInput()' + NL + '        toolAbility()' + NL + '    }',
         '        tokens("gpt", "5", "3")' + NL + '        visionInput()' + NL + '        toolAbility()' + NL + '        contextLength(400_000)' + NL + '    }'),
        ('        tokens("gpt", "5", "4")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("gpt", "5", "4")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(400_000)' + NL + '    }'),
        ('        tokens("gpt", "5", "4", "mini")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("gpt", "5", "4", "mini")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(400_000)' + NL + '    }'),
        ('        tokens("gpt", "5", "4", "nano")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("gpt", "5", "4", "nano")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(400_000)' + NL + '    }'),
        ('        tokens("gpt", "5", "5")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("gpt", "5", "5")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_048_576)' + NL + '    }'),
        ('        tokens("gpt", "5", "6")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("gpt", "5", "6")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_048_576)' + NL + '    }'),
        ('        tokens("gpt", "6")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("gpt", "6")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_048_576)' + NL + '    }'),
        ('        tokens("gemini", "2", "0", "flash")' + NL + '        visionInput()' + NL + '        toolAbility()' + NL + '    }',
         '        tokens("gemini", "2", "0", "flash")' + NL + '        visionInput()' + NL + '        toolAbility()' + NL + '        contextLength(1_048_576)' + NL + '    }'),
        ('        tokens("gemini", "2", "5", "flash")' + NL + '        notTokens("image")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("gemini", "2", "5", "flash")' + NL + '        notTokens("image")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_048_576)' + NL + '    }'),
        ('        tokens("gemini", "2", "5", "pro")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("gemini", "2", "5", "pro")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_048_576)' + NL + '    }'),
        ('        tokens("gemini", "3", "pro")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("gemini", "3", "pro")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_048_576)' + NL + '    }'),
        ('        tokens("gemini", "3", "flash")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("gemini", "3", "flash")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_048_576)' + NL + '    }'),
        ('        tokens("gemini", "3", "1", "pro", "preview")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("gemini", "3", "1", "pro", "preview")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_048_576)' + NL + '    }'),
        ('        tokens("gemini", "3", "1", "pro", "preview", "customtools")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("gemini", "3", "1", "pro", "preview", "customtools")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_048_576)' + NL + '    }'),
        ('        tokens("gemini", "3", "5")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("gemini", "3", "5")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_048_576)' + NL + '    }'),
        ('        exact("gemini-flash-latest")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        exact("gemini-flash-latest")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_048_576)' + NL + '    }'),
        ('        exact("gemini-pro-latest")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        exact("gemini-pro-latest")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_048_576)' + NL + '    }'),
        ('        tokens("claude", "3", "5", "sonnet")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("claude", "3", "5", "sonnet")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(200_000)' + NL + '    }'),
        ('        tokens("claude", "3", "7", "sonnet")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("claude", "3", "7", "sonnet")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(200_000)' + NL + '    }'),
        ('        tokens("claude", "4")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("claude", "4")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(200_000)' + NL + '    }'),
        ('        tokens("claude", "4", "5")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("claude", "4", "5")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(200_000)' + NL + '    }'),
        ('        tokens("claude", "sonnet", "4", "6")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("claude", "sonnet", "4", "6")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("claude", "opus", "4", "6")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("claude", "opus", "4", "6")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("claude", "opus", "4", "7")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("claude", "opus", "4", "7")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("claude", "opus", "4", "8")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("claude", "opus", "4", "8")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("claude", "sonnet", "5")' + NL + '        notTokens("claude", "sonnet", "4")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("claude", "sonnet", "5")' + NL + '        notTokens("claude", "sonnet", "4")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("claude", "opus", "5")' + NL + '        notTokens("claude", "opus", "4")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("claude", "opus", "5")' + NL + '        notTokens("claude", "opus", "4")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("deepseek", "v", "3")' + NL + '        toolAbility()' + NL + '    }',
         '        tokens("deepseek", "v", "3")' + NL + '        toolAbility()' + NL + '        contextLength(128_000)' + NL + '    }'),
        ('        tokens("deepseek", "chat")' + NL + '        toolAbility()' + NL + '    }',
         '        tokens("deepseek", "chat")' + NL + '        toolAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("deepseek", "r", "1")' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("deepseek", "r", "1")' + NL + '        toolReasoningAbility()' + NL + '        contextLength(128_000)' + NL + '    }'),
        ('        tokens("deepseek", "reasoner")' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("deepseek", "reasoner")' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("deepseek", "v", "4", "flash")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("deepseek", "v", "4", "flash")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("deepseek", "v", "4", "flash", "vision", "exp")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("deepseek", "v", "4", "flash", "vision", "exp")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("deepseek", "v", "4", "pro")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("deepseek", "v", "4", "pro")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("deepseek", "flash")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("deepseek", "flash")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("deepseek", "v", "4", "1", "flash")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("deepseek", "v", "4", "1", "flash")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("deepseek", "v", "3", "1")' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("deepseek", "v", "3", "1")' + NL + '        toolReasoningAbility()' + NL + '        contextLength(128_000)' + NL + '    }'),
        ('        tokens("deepseek", "v", "3", "2")' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("deepseek", "v", "3", "2")' + NL + '        toolReasoningAbility()' + NL + '        contextLength(128_000)' + NL + '    }'),
        ('        tokens("qwen", "3")' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("qwen", "3")' + NL + '        toolReasoningAbility()' + NL + '        contextLength(128_000)' + NL + '    }'),
        ('        tokens("qwen", "3", "5")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("qwen", "3", "5")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("qwen", "3", "6")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("qwen", "3", "6")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("qwen", "3", "7")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("qwen", "3", "7")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("qwen", "3", "8")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("qwen", "3", "8")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("qwen", "3", "5", "max")' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("qwen", "3", "5", "max")' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("qwen", "3", "6", "max")' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("qwen", "3", "6", "max")' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("qwen", "3", "7", "max")' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("qwen", "3", "7", "max")' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("qwen", "3", "8", "max")' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("qwen", "3", "8", "max")' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("doubao", "1", "6")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("doubao", "1", "6")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(256_000)' + NL + '    }'),
        ('        tokens("doubao", "1", "8")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("doubao", "1", "8")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(256_000)' + NL + '    }'),
        ('        tokens("doubao", "2", "0")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("doubao", "2", "0")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(256_000)' + NL + '    }'),
        ('        tokens("doubao", "2", "1")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("doubao", "2", "1")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(256_000)' + NL + '    }'),
        ('        tokens("grok", "4")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("grok", "4")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(256_000)' + NL + '    }'),
        ('        tokens("kimi", "k", "2")' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("kimi", "k", "2")' + NL + '        toolReasoningAbility()' + NL + '        contextLength(128_000)' + NL + '    }'),
        ('        tokens("kimi", "k", "2", "5")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("kimi", "k", "2", "5")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(256_000)' + NL + '    }'),
        ('        tokens("kimi", "k", "2", "6")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("kimi", "k", "2", "6")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(256_000)' + NL + '    }'),
        ('        tokens("kimi", "k", "3")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("kimi", "k", "3")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        exact("k3")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        exact("k3")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("step", "3")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("step", "3")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(128_000)' + NL + '    }'),
        ('        tokens("step", "3", "7", "flash")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("step", "3", "7", "flash")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(256_000)' + NL + '    }'),
        ('        tokens("step", "5")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("step", "5")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("glm", "4", "5")' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("glm", "4", "5")' + NL + '        toolReasoningAbility()' + NL + '        contextLength(128_000)' + NL + '    }'),
        ('        tokens("glm", "4", "6")' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("glm", "4", "6")' + NL + '        toolReasoningAbility()' + NL + '        contextLength(200_000)' + NL + '    }'),
        ('        tokens("glm", "4", "7")' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("glm", "4", "7")' + NL + '        toolReasoningAbility()' + NL + '        contextLength(200_000)' + NL + '    }'),
        ('        tokens("glm", "5")' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("glm", "5")' + NL + '        toolReasoningAbility()' + NL + '        contextLength(200_000)' + NL + '    }'),
        ('        tokens("glm", "5", "1")' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("glm", "5", "1")' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("glm", "5", "2")' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("glm", "5", "2")' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("glm", "5", "3")' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("glm", "5", "3")' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("glm", "5", "3", "flash")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("glm", "5", "3", "flash")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("minimax", "m", "2")' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("minimax", "m", "2")' + NL + '        toolReasoningAbility()' + NL + '        contextLength(204_800)' + NL + '    }'),
        ('        tokens("minimax", "m", "2", "5")' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("minimax", "m", "2", "5")' + NL + '        toolReasoningAbility()' + NL + '        contextLength(204_800)' + NL + '    }'),
        ('        tokens("minimax", "m", "2", "7")' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("minimax", "m", "2", "7")' + NL + '        toolReasoningAbility()' + NL + '        contextLength(204_800)' + NL + '    }'),
        ('        tokens("minimax", "m", "3")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("minimax", "m", "3")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(1_000_000)' + NL + '    }'),
        ('        tokens("mimo", "v", "2", "6")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("mimo", "v", "2", "6")' + NL + '        visionInput()' + NL + '        toolReasoningAbility()' + NL + '        contextLength(208_000)' + NL + '    }'),
        ('        tokens("hy", "3")' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("hy", "3")' + NL + '        toolReasoningAbility()' + NL + '        contextLength(256_000)' + NL + '    }'),
        ('        tokens("hy", "4")' + NL + '        toolReasoningAbility()' + NL + '    }',
         '        tokens("hy", "4")' + NL + '        toolReasoningAbility()' + NL + '        contextLength(256_000)' + NL + '    }'),
    ]

    applied = 0
    for old, new in INFUSIONS:
        if old in r:
            r = r.replace(old, new, 1)
            applied += 1
        else:
            fail(REG, 'infusion anchor not found: ' + old[:80])
    if applied < 80:
        fail(REG, 'too few infusions applied: ' + str(applied))
    (ROOT / REG).write_text(r, encoding='utf-8')
    print('batch52: ModelRegistry OK (' + str(applied) + ' models infused)')
else:
    print('batch52: ModelRegistry already applied')

print('batch52 v2: OK')
