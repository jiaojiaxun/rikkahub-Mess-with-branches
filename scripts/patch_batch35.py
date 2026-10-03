#!/usr/bin/env python3
"""batch35 v3: 大肥鱼 C+D 接线（修复 #115 两处编译错误）

v3 修复（#115 教训）：
1. ThemePage 锚点必须吃掉旧 item 的闭合 ')'——v2 只停到 '},'，
   新 item 被插进旧 item 的参数列表内 → mixing named/positional (行101)
   真实结构：onCheckedChange = { amoledDarkMode = it }   <- } 闭 lambda
             )                                            <- ) 闭 Switch
             },                                           <- } 闭 trailingContent
             )                                            <- ) 闭 item  <= v2 漏了
2. AssistantPage 弃用懒匹配正则——v2 的 [\s\S]*?\), 越过 AssistantImporter
   （它后面是 ')' 换行 '}'，没有 '),'）一路吃到下行 Row 的 '),'，
   把 TextButton 插进 Row 参数区 → horizontalArrangement on Unit 等一串错。
   v3 改用真实源码逐字节 str.find 精确匹配，找不到即 fail。
3. 去掉 ThemePage 重复 dp import（原文已有 dp，只缺 layout.size）。
4. DisplaySetting 部分 #114/#115 两次通过，保持幂等原样。

铁律：不用 f-string；含 Kotlin 双引号的块用 Python 单引号字符串；幂等标记 rhWhalePreset
"""
from pathlib import Path
import re

ROOT = Path.cwd()

def fail(path, msg):
    print('::error file=' + path + '::batch35 ' + msg[:1400])
    raise SystemExit(1)

# --- 1. DisplaySetting 加 mascotEnabled 字段（两次 CI 已验证通过，保持） ---
P_DS = "app/src/main/java/me/rerere/rikkahub/data/datastore/PreferencesStore.kt"
t_ds = (ROOT / P_DS).read_text(encoding="utf-8")

if "mascotEnabled" in t_ds:
    print("batch35: DisplaySetting already has mascotEnabled")
else:
    ANCHOR_DS = re.compile(r'(val\s+showLineNumbers:\s*Boolean\s*=\s*false\s*,)')
    m = ANCHOR_DS.search(t_ds)
    if not m:
        fail(P_DS, "DisplaySetting.showLineNumbers anchor not found")
    insertion = m.group(1) + '\n    val mascotEnabled: Boolean = false, // rhWhalePreset\n'
    t_ds = t_ds[:m.start()] + insertion + t_ds[m.end():]
    (ROOT / P_DS).write_text(t_ds, encoding="utf-8")
    print("batch35: DisplaySetting.mascotEnabled added")

# --- 2. SettingPreferencesThemePage 加吉祥物开关 + 预览 ---
P_THEME = "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPreferencesThemePage.kt"
t_theme = (ROOT / P_THEME).read_text(encoding="utf-8")

if "rhWhalePreset" in t_theme:
    print("batch35: ThemePage already has mascot switch")
else:
    ANCHOR_THEME = re.compile(
        r'(amoledDarkMode\s*=\s*it\s*\}\s*\n\s*\)\s*\n\s*\}\s*,\s*\n\s*\))'
    )
    m = ANCHOR_THEME.search(t_theme)
    if not m:
        fail(P_THEME, "amoledDarkMode Switch + item close anchor not found")
    new_items = (
        m.group(1) + '\n'
        '                    item(\n'
        '                        headlineContent = { Text("吉祥物") },\n'
        '                        supportingContent = { Text("在设置页预览蓝色大肥鱼吉祥物") },\n'
        '                        trailingContent = {\n'
        '                            Switch(\n'
        '                                checked = settings.displaySetting.mascotEnabled,\n'
        '                                onCheckedChange = {\n'
        '                                    vm.updateSettings(settings.copy(\n'
        '                                        displaySetting = settings.displaySetting.copy(mascotEnabled = it)\n'
        '                                    ))\n'
        '                                }\n'
        '                            )\n'
        '                        },\n'
        '                    )\n'
        '                    item(\n'
        '                        headlineContent = { Text("吉祥物预览") },\n'
        '                        supportingContent = {\n'
        '                            WhaleGirlMascot(\n'
        '                                state = MiffanMascotState.Idle,\n'
        '                                interactive = true,\n'
        '                                modifier = Modifier.size(120.dp),\n'
        '                            )\n'
        '                        },\n'
        '                    )\n'
    )
    t_theme = t_theme[:m.start()] + new_items + t_theme[m.end():]
    # 只补真正缺的 import：layout.size（dp 原文已有，勿重复注入）
    if 'import androidx.compose.foundation.layout.size\n' not in t_theme:
        t_theme = t_theme.replace(
            "import androidx.compose.foundation.layout.padding\n",
            "import androidx.compose.foundation.layout.padding\n"
            "import androidx.compose.foundation.layout.size\n",
            1,
        )
    if 'import me.rerere.rikkahub.ui.components.ui.WhaleGirlMascot\n' not in t_theme:
        t_theme = t_theme.replace(
            "import me.rerere.rikkahub.ui.components.ui.CardGroup\n",
            "import me.rerere.rikkahub.ui.components.ui.CardGroup\n"
            "import me.rerere.rikkahub.ui.components.ui.WhaleGirlMascot\n"
            "import me.rerere.rikkahub.ui.components.ui.MiffanMascotState\n",
            1,
        )
    (ROOT / P_THEME).write_text(t_theme, encoding="utf-8")
    print("batch35: ThemePage mascot switch + preview added")

# --- 3. AssistantPage 加"使用蓝色大肥鱼预设"按钮（精确匹配，非正则） ---
P_ASST = "app/src/main/java/me/rerere/rikkahub/ui/pages/assistant/AssistantPage.kt"
t_asst = (ROOT / P_ASST).read_text(encoding="utf-8")

if "rhWhalePreset" in t_asst:
    print("batch35: AssistantPage already has whale preset button")
else:
    EXACT_BLOCK = (
        '                    AssistantImporter(\n'
        '                        onUpdate = {\n'
        '                            update(it)\n'
        '                            state.confirm()\n'
        '                        },\n'
        '                        modifier = Modifier.fillMaxWidth(),\n'
        '                    )\n'
    )
    idx = t_asst.find(EXACT_BLOCK)
    if idx < 0:
        fail(P_ASST, "AssistantImporter exact block not found (source changed?)")
    insert_at = idx + len(EXACT_BLOCK)
    new_btn = (
        '                    TextButton(\n'
        '                        onClick = {\n'
        '                            update(createWhaleAssistant())\n'
        '                            state.confirm()\n'
        '                        }\n'
        '                    ) {\n'
        '                        Text("使用蓝色大肥鱼预设")\n'
        '                    }\n'
    )
    t_asst = t_asst[:insert_at] + new_btn + t_asst[insert_at:]
    if 'import me.rerere.rikkahub.data.model.createWhaleAssistant\n' not in t_asst:
        t_asst = t_asst.replace(
            "import me.rerere.rikkahub.data.model.Assistant\n",
            "import me.rerere.rikkahub.data.model.Assistant\n"
            "import me.rerere.rikkahub.data.model.createWhaleAssistant\n",
            1,
        )
    (ROOT / P_ASST).write_text(t_asst, encoding="utf-8")
    print("batch35: AssistantPage whale preset button added")

print("batch35: OK")
