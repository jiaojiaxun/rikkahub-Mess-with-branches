#!/usr/bin/env python3
'''batch42 v3: 设置-供应商搜索框支持搜 API Key / BaseUrl

#134 编译错误：Unresolved reference 'apiKey' / 'baseUrl' on receiver of type 'ProviderSetting'。
根因：ProviderSetting 是 sealed class，只有 name 是抽象属性，apiKey/baseUrl 只挂在各子类
（如 ProviderSetting.OpenAI）上。

v3 不再手写字段引用，而是让脚本自己读 ProviderSetting.kt，把「确实同时声明了
apiKey / baseUrl」的子类全部挑出来，自动生成 when 分支：
- 字段只在该子类体内出现才生成对应那一半，不会引用不存在的字段。
- 一个都没挑到时退回 provider.toString()（data class toString 一定包含这些值）。
'''
from pathlib import Path
import re

ROOT = Path.cwd()
P = "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingProviderPage.kt"
PS = "ai/src/main/java/me/rerere/ai/provider/ProviderSetting.kt"
MARK = "rhProviderSearch"


def fail(msg):
    print('::error file=' + P + '::batch42 ' + msg[:1500])
    raise SystemExit(1)


# --- 定位 ProviderSetting.kt ---
ps_path = None
if (ROOT / PS).exists():
    ps_path = ROOT / PS
else:
    for p in ROOT.rglob("ProviderSetting.kt"):
        sp = str(p)
        if sp.startswith("build/") or "/build/" in sp:
            continue
        ps_path = p
        break
if ps_path is None:
    fail("cannot locate ProviderSetting.kt")

src = ps_path.read_text(encoding="utf-8", errors="ignore")
if "sealed class ProviderSetting" not in src:
    fail("ProviderSetting.kt does not declare a sealed class ProviderSetting")

# --- 挑出所有 : ProviderSetting() 的嵌套 data class，检查其是否真的带 apiKey / baseUrl ---
pat = re.compile(r"data class (\w+)\(\s*(.*?)\n    \) : ProviderSetting\(\)", re.S)
branches = []
for m in pat.finditer(src):
    name, body = m.group(1), m.group(2)
    parts = []
    if re.search(r"\bvar apiKey\b", body):
        parts.append("provider.apiKey")
    if re.search(r"\bvar baseUrl\b", body):
        parts.append("provider.baseUrl")
    if parts:
        branches.append("        is ProviderSetting." + name + " -> " + ' + " " + '.join(parts))

print("::notice::subclasses with apiKey/baseUrl = " + str(len(branches)))
for b in branches:
    print("::notice::  " + b.strip())

if branches:
    helper = (
        "// rhProviderSearch: ProviderSetting 是 sealed class，apiKey/baseUrl 只挂在各子类上，\n"
        "// 这里按实际子类提取，避免对不存在的字段做引用。\n"
        "private fun providerSearchExtra(provider: ProviderSetting): String =\n"
        "    when (provider) {\n"
        + "\n".join(branches) + "\n"
        "        else -> \"\"\n"
        "    }\n\n"
    )
    extra_call = "providerSearchExtra(provider).contains(q, ignoreCase = true)"
else:
    print("::warning::no subclass declares apiKey/baseUrl; falling back to toString()")
    helper = (
        "// rhProviderSearch: 未在 ProviderSetting 子类里找到 apiKey/baseUrl 字段，\n"
        "// 退回 data class 的 toString()（它一定包含这些值）。\n"
        "private fun providerSearchExtra(provider: ProviderSetting): String = provider.toString()\n\n"
    )
    extra_call = "providerSearchExtra(provider).contains(q, ignoreCase = true)"

# --- 插入 helper（放在最后一个 import 之后、第一个 @Composable 之前）---
t = (ROOT / P).read_text(encoding="utf-8")
if MARK in t:
    print("batch42: already applied")
    raise SystemExit(0)

A0 = '''@Composable
fun SettingProviderPage(vm: SettingVM = koinViewModel()) {
'''
if A0 not in t:
    fail("anchor SettingProviderPage not found")
t = t.replace(A0, helper + A0, 1)

# --- 改过滤条件 ---
A1 = '''    val filteredProviders = remember(settings.providers, searchQuery) {
        if (searchQuery.isBlank()) {
            settings.providers
        } else {
            settings.providers.filter { provider ->
                provider.name.contains(searchQuery, ignoreCase = true)
            }
        }
    }
'''
if A1 not in t:
    fail("anchor filteredProviders not found")

add1 = '''    // rhProviderSearch: 搜索框同时匹配 供应商名 / API Key / BaseUrl
    val filteredProviders = remember(settings.providers, searchQuery) {
        if (searchQuery.isBlank()) {
            settings.providers
        } else {
            val q = searchQuery.trim()
            settings.providers.filter { provider ->
                provider.name.contains(q, ignoreCase = true) ||
                    ''' + extra_call + '''
            }
        }
    }
'''
t = t.replace(A1, add1, 1)

for r in [MARK, "private fun providerSearchExtra(provider: ProviderSetting)", "val q = searchQuery.trim()"]:
    if r not in t:
        fail("selfcheck missing " + repr(r))

if "provider.apiKey" in t and "is ProviderSetting." not in t:
    fail("generated apiKey reference without when branch")

(ROOT / P).write_text(t, encoding="utf-8")
print("batch42 v3: OK, branches=" + str(len(branches)))