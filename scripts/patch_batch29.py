#!/usr/bin/env python3
"""Register the whale-girl preset theme (batch A1).

Writes presets/WhaleTheme.kt and registers it in PresetTheme.kt plus the string
resources. All edits are anchored and idempotent: a missing anchor prints
::error and exits 1 so the CI job stops instead of silently doing nothing.

Anchors used (all regex, because the exact formatting of the existing presets is
not ours to control):
  * PresetTheme.kt  -> "import ...presets.SakuraThemePreset" and the listOf( block
  * strings.xml     -> a known theme_name_* entry, inserted right after it
"""
import re
import sys
from pathlib import Path

PRESET_DIR = Path("app/src/main/java/me/rerere/rikkahub/ui/theme/presets")
PRESET_REGISTRY = Path("app/src/main/java/me/rerere/rikkahub/ui/theme/PresetTheme.kt")
STRINGS_DEFAULT = Path("app/src/main/res/values/strings.xml")
STRINGS_ZH = Path("app/src/main/res/values-zh/strings.xml")

THEME_ID = "whale_girl"
WHALE_THEME = PRESET_DIR / "WhaleTheme.kt"

# Colours copied verbatim from Ayuilos/Miffan WhaleTheme.kt (commit ade291c, AGPL-3.0).
THEME_SOURCE = '''package me.rerere.rikkahub.ui.theme.presets

import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import me.rerere.rikkahub.R
import me.rerere.rikkahub.ui.theme.PresetTheme

/**
 * Whale girl preset theme ("{id}").
 *
 * Vendored from Ayuilos/Miffan (AGPL-3.0), commit ade291c.
 * Copyright (c) Ayuilos and the RikkaHub / Miffan contributors.
 * Upstream: https://github.com/Ayuilos/Miffan
 *
 * Clear blue by day, deep ocean by night; text keeps strong contrast in both.
 */
val WhaleThemePreset by lazy {{
    PresetTheme(
        id = "{id}",
        name = {{ Text(stringResource(id = R.string.theme_name_whale)) }},
        standardLight = lightColorScheme(
            primary = Color(0xFF285AD5), onPrimary = Color.White,
            primaryContainer = Color(0xFFDCE6FF), onPrimaryContainer = Color(0xFF123A88),
            secondary = Color(0xFF49617D), onSecondary = Color.White,
            secondaryContainer = Color(0xFFD9E8FC), onSecondaryContainer = Color(0xFF29425D),
            tertiary = Color(0xFF62558F), onTertiary = Color.White,
            tertiaryContainer = Color(0xFFE9DDFF), onTertiaryContainer = Color(0xFF453772),
            background = Color(0xFFF8FAFF), onBackground = Color(0xFF192334),
            surface = Color(0xFFF8FAFF), onSurface = Color(0xFF192334),
            surfaceVariant = Color(0xFFE0E7F3), onSurfaceVariant = Color(0xFF444F62),
            outline = Color(0xFF737F92), outlineVariant = Color(0xFFC3CDDF),
            inverseSurface = Color(0xFF2D3749), inverseOnSurface = Color(0xFFEDF2FF),
            inversePrimary = Color(0xFFADC6FF),
            surfaceDim = Color(0xFFD7DFEE), surfaceBright = Color(0xFFF8FAFF),
            surfaceContainerLowest = Color.White,
            surfaceContainerLow = Color(0xFFF0F5FF),
            surfaceContainer = Color(0xFFEAF0FC),
            surfaceContainerHigh = Color(0xFFE4EBF8),
            surfaceContainerHighest = Color(0xFFDEE5F2),
        ),
        standardDark = darkColorScheme(
            primary = Color(0xFFADC6FF), onPrimary = Color(0xFF082D70),
            primaryContainer = Color(0xFF20468F), onPrimaryContainer = Color(0xFFDCE6FF),
            secondary = Color(0xFFB0C9E7), onSecondary = Color(0xFF18324C),
            secondaryContainer = Color(0xFF304A65), onSecondaryContainer = Color(0xFFD9E8FC),
            tertiary = Color(0xFFCDBDF7), onTertiary = Color(0xFF352658),
            tertiaryContainer = Color(0xFF4C3E70), onTertiaryContainer = Color(0xFFE9DDFF),
            background = Color(0xFF0D1526), onBackground = Color(0xFFE0E7F5),
            surface = Color(0xFF0D1526), onSurface = Color(0xFFE0E7F5),
            surfaceVariant = Color(0xFF3F4B61), onSurfaceVariant = Color(0xFFC2CDDF),
            outline = Color(0xFF8D9AB0), outlineVariant = Color(0xFF3F4B61),
            inverseSurface = Color(0xFFE0E7F5), inverseOnSurface = Color(0xFF283245),
            inversePrimary = Color(0xFF285AD5),
            surfaceDim = Color(0xFF0D1526), surfaceBright = Color(0xFF333F55),
            surfaceContainerLowest = Color(0xFF080F1D),
            surfaceContainerLow = Color(0xFF141F32),
            surfaceContainer = Color(0xFF192538),
            surfaceContainerHigh = Color(0xFF243045),
            surfaceContainerHighest = Color(0xFF2E3B50),
        ),
    )
}}
'''


def fail(script: str, message: str) -> int:
    print(f"::error file={script}::{message}", file=sys.stderr)
    return 1


def ensure_theme_file() -> int:
    if WHALE_THEME.exists() and f'id = "{THEME_ID}"' in WHALE_THEME.read_text(encoding="utf-8"):
        print("== WhaleTheme.kt already present", flush=True)
        return 0
    PRESET_DIR.mkdir(parents=True, exist_ok=True)
    WHALE_THEME.write_text(THEME_SOURCE.format(id=THEME_ID), encoding="utf-8")
    print(f"wrote {WHALE_THEME}", flush=True)
    return 0


def patch_registry() -> int:
    src = PRESET_REGISTRY.read_text(encoding="utf-8")
    if "WhaleThemePreset" in src:
        print("== PresetTheme.kt already registers WhaleThemePreset", flush=True)
        return 0

    import_anchor = "import me.rerere.rikkahub.ui.theme.presets.SakuraThemePreset"
    if import_anchor not in src:
        return fail("scripts/patch_batch29.py",
                    "import anchor not found in PresetTheme.kt: " + import_anchor)
    src = src.replace(
        import_anchor,
        "import me.rerere.rikkahub.ui.theme.presets.WhaleThemePreset\n" + import_anchor,
        1,
    )

    # Append to the PresetThemes list; anchor on the last known registration line.
    list_anchor = re.search(r"(\n(\s*)ClaudeThemePreset,?\n\s*\))", src)
    if list_anchor is None:
        return fail("scripts/patch_batch29.py",
                    "PresetThemes listOf block not found in PresetTheme.kt")
    indent = list_anchor.group(2)
    src = src[:list_anchor.start(1)] + \
        f"\n{indent}WhaleThemePreset,\n{indent})" + src[list_anchor.end(1):]

    PRESET_REGISTRY.write_text(src, encoding="utf-8")
    print("patched PresetTheme.kt (import + list)", flush=True)
    return 0


def patch_strings(path: Path, name: str, value: str, script: str) -> int:
    if not path.exists():
        print(f"== {path} not present, skipping", flush=True)
        return 0
    src = path.read_text(encoding="utf-8")
    if f'name="{name}"' in src:
        print(f"== {path} already has {name}", flush=True)
        return 0
    anchor = re.search(r'^[ \t]*<string name="theme_name_[^"]+">[^<]*</string>[ \t]*$',
                       src, re.MULTILINE)
    if anchor is None:
        return fail(script, f"theme_name_* anchor not found in {path}")
    line = f'  <string name="{name}">{value}</string>'
    src = src[:anchor.end()] + "\n" + line + src[anchor.end():]
    path.write_text(src, encoding="utf-8")
    print(f"patched {path} (+{name})", flush=True)
    return 0


def main() -> int:
    script = "scripts/patch_batch29.py"
    if not PRESET_REGISTRY.exists():
        return fail(script, f"missing {PRESET_REGISTRY}")
    for step in (ensure_theme_file, patch_registry):
        code = step()
        if code != 0:
            return code
    for path, value in ((STRINGS_DEFAULT, "Blue Whale"), (STRINGS_ZH, "蓝色大肥鱼")):
        code = patch_strings(path, "theme_name_whale", value, script)
        if code != 0:
            return code
    print("whale-girl theme registered", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())