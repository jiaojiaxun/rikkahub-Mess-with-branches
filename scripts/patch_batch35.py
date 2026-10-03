#!/usr/bin/env python3
"""batch35: 大肥鱼 C+D 接线（三处改动）

1. DisplaySetting 加 mascotEnabled 字段
2. SettingPreferencesThemePage 加吉祥物开关 + 120dp 预览
3. AssistantPage 创建对话框加"使用蓝色大肥鱼预设"按钮

铁律遵守：
- 不用 f-string（batch32 教训）
- 锚点用行级正则 + [\\s\\S]*? 容错（#114 教训：精确空白匹配太脆）
- 幂等标记特异（mascotEnabled / rhWhalePreset）
- Kotlin 含双引号的代码块用 Python 单引号字符串（避免 SyntaxError）
"""
from pathlib import Path
import re

ROOT = Path.cwd()

def fail(path, msg):
    print('::error file=' + path + '::batch35 ' + msg[:1400])
    raise SystemExit(1)

# --- 1. DisplaySetting 加 mascotEnabled 字段 ---
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
    # 实际代码结构：amoledDarkMode = it }\n)\n},
    # } 闭 lambda, ) 闭 Switch, } 闭 trailingContent, , 闭 item
    ANCHOR_THEME = re.compile(r'(amoledDarkMode\s*=\s*it\s*\}\s*\n\s*\)\s*\n\s*\}\s*,)')
    m = ANCHOR_THEME.search(t_theme)
    if not m:
        fail(P_THEME, "amoledDarkMode Switch anchor not found")
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
    # 加 import
    t_theme = t_theme.replace(
        "import me.rerere.rikkahub.ui.components.ui.CardGroup",
        "import me.rerere.rikkahub.ui.components.ui.CardGroup\n"
        "import me.rerere.rikkahub.ui.components.ui.WhaleGirlMascot\n"
        "import me.rerere.rikkahub.ui.components.ui.MiffanMascotState\n"
        "import androidx.compose.foundation.layout.size\n"
        "import androidx.compose.ui.unit.dp",
    )
    (ROOT / P_THEME).write_text(t_theme, encoding="utf-8")
    print("batch35: ThemePage mascot switch + preview added")

# --- 3. AssistantPage 创建对话框加"使用蓝色大肥鱼预设"按钮 ---
P_ASST = "app/src/main/java/me/rerere/rikkahub/ui/pages/assistant/AssistantPage.kt"
t_asst = (ROOT / P_ASST).read_text(encoding="utf-8")

if "rhWhalePreset" in t_asst:
    print("batch35: AssistantPage already has whale preset button")
else:
    # #114 教训：精确空白匹配 \s*\n\s* 太脆，改用 [\s\S]*? 非贪婪通配
    ANCHOR_ASST = re.compile(r'(AssistantImporter\([\s\S]*?fillMaxWidth\(\)[\s\S]*?\),)')
    m = ANCHOR_ASST.search(t_asst)
    if not m:
        fail(P_ASST, "AssistantImporter anchor not found")
    new_btn = (
        m.group(1) + '\n'
        '                    TextButton(\n'
        '                        onClick = {\n'
        '                            update(createWhaleAssistant())\n'
        '                            state.confirm()\n'
        '                        }\n'
        '                    ) {\n'
        '                        Text("使用蓝色大肥鱼预设")\n'
        '                    }\n'
    )
    t_asst = t_asst[:m.start()] + new_btn + t_asst[m.end():]
    # 加 import
    t_asst = t_asst.replace(
        "import me.rerere.rikkahub.data.model.Assistant\n",
        "import me.rerere.rikkahub.data.model.Assistant\n"
        "import me.rerere.rikkahub.data.model.createWhaleAssistant\n",
    )
    (ROOT / P_ASST).write_text(t_asst, encoding="utf-8")
    print("batch35: AssistantPage whale preset button added")

print("batch35: OK")
