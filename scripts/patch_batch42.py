#!/usr/bin/env python3
'''batch42 v4: 设置-供应商搜索框支持搜 API Key / BaseUrl

#136 编译错误回顾：
  Unresolved reference 'BalanceOption' / 'apiKey' / 'baseUrl' on receiver of type 'ProviderSetting'
根因：v3 用非贪婪正则 data class (\\w+)\\(\\s*(.*?)\\n    \\) : ProviderSetting\\(\\) 配对，
而 BalanceOption 是文件最前面的顶层 data class，它的参数列表里没有嵌套括号，
于是 \\s* 直接跨过整个 BalanceOption 一路吃到第一个 : ProviderSetting()（即 OpenAI），
把 BalanceOption 误认成 ProviderSetting 的子类，生成了不存在的 ProviderSetting.BalanceOption。

v4 改为括号配对扫描：对每个 data class Name( 逐字符数括号深度，找到真正配对的 ')'，
再看它后面是否紧跟 ": ProviderSetting("，是才算子类。这样嵌套类型
（例如 description: @Composable (() -> Unit)）不会再破坏配对。
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


def find_subclasses(src):
    """括号配对扫描：返回 [(name, params), ...]，只包含真正嵌套在 ProviderSetting 下的子类。"""
    sealed_at = src.find("sealed class ProviderSetting")
    if sealed_at < 0:
        return []
    res = []
    for m in re.finditer(r"data class (\w+)\s*\(", src):
        if m.start() < sealed_at:
            continue  # sealed class 之前的 data class 是顶层类，不可能是子类
        i = m.end()
        depth = 1
        while i < len(src) and depth > 0:
            c = src[i]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            i += 1
        if depth != 0:
            continue
        params = src[m.end():i - 1]
        if re.match(r"\s*:\s*ProviderSetting\s*\(", src[i:i + 60]):
            res.append((m.group(1), params))
    return res


ps_path = ROOT / PS
if not ps_path.exists():
    hit = None
    for p in ROOT.rglob("ProviderSetting.kt"):
        sp = str(p)
        if sp.startswith("build/") or "/build/" in sp:
            continue
        hit = p
        break
    if hit is None:
        fail("cannot locate ProviderSetting.kt")
    ps_path = hit

src = ps_path.read_text(encoding="utf-8", errors="ignore")
if "sealed class ProviderSetting" not in src:
    fail("ProviderSetting.kt does not declare a sealed class ProviderSetting")

subs = find_subclasses(src)
print("::notice::nested subclasses found = " + str(len(subs)) + " : " + ",".join(n for n, _ in subs))

branches = []
seen = set()
for name, params in subs:
    if name in seen:
        continue
    parts = []
    if re.search(r"\bvar apiKey\b", params):
        parts.append("provider.apiKey")
    if re.search(r"\bvar baseUrl\b", params):
        parts.append("provider.baseUrl")
    if not parts:
        continue
    seen.add(name)
    branches.append("        is ProviderSetting." + name + " -> " + ' + " " + '.join(parts))

print("::notice::branches = " + str(len(branches)))
for b in branches:
    print("::notice::  " + b.strip())

if not branches:
    print("::warning::no subclass declares apiKey/baseUrl; falling back to toString()")
    helper = (
        "// rhProviderSearch: 未在 ProviderSetting 子类里找到 apiKey/baseUrl 字段，\n"
        "// 退回 data class 的 toString()（它一定包含这些值）。\n"
        "private fun providerSearchExtra(provider: ProviderSetting): String = provider.toString()\n\n"
    )
else:
    helper = (
        "// rhProviderSearch: ProviderSetting 是 sealed class，apiKey/baseUrl 只挂在各子类上，\n"
        "// 这里按实际子类提取，避免对不存在的字段做引用。\n"
        "private fun providerSearchExtra(provider: ProviderSetting): String =\n"
        "    when (provider) {\n"
        + "\n".join(branches) + "\n"
        "        else -> \"\"\n"
        "    }\n\n"
    )

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
                    providerSearchExtra(provider).contains(q, ignoreCase = true)
            }
        }
    }
'''
t = t.replace(A1, add1, 1)

for r in [MARK, "private fun providerSearchExtra(provider: ProviderSetting)", "val q = searchQuery.trim()"]:
    if r not in t:
        fail("selfcheck missing " + repr(r))

for b in branches:
    if b not in t:
        fail("branch lost during write: " + b.strip())

(ROOT / P).write_text(t, encoding="utf-8")
print("batch42 v4: OK, branches=" + str(len(branches)))