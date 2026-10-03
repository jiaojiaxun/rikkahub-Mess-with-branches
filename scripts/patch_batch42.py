#!/usr/bin/env python3
'''batch42 v2: 设置-供应商 搜索框支持搜 API Key 和 BaseUrl

v1 失败原因：前置校验写死扫描 ai/ 目录，但该模块不叫 ai，
-> "cannot locate data class ProviderSetting in ai module" -> patch 步骤退出 1。

v2 改为全仓库 rglob 扫描（排除 build/），并在找不到时打印候选文件与顶层目录，
方便下一轮直接定位。字段校验只在真的找到类且缺字段时才 fail-fast。
'''
from pathlib import Path
import re

ROOT = Path.cwd()
P = "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingProviderPage.kt"
MARK = "rhProviderSearch"


def fail(msg):
    print('::error file=' + P + '::batch42 ' + msg[:1200])
    raise SystemExit(1)


# --- 扫顶层目录，顺手记下来备查 ---
try:
    tops = sorted(x.name for x in ROOT.iterdir() if x.is_dir())
    print("::notice::root dirs = " + ",".join(tops))
except Exception as e:
    print("::notice::root listing failed: " + str(e))

# --- 全仓库定位 ProviderSetting ---
cls = None
soft = []
for p in ROOT.rglob("*.kt"):
    sp = str(p)
    if sp.startswith("build/") or "/build/" in sp or "/.git/" in sp:
        continue
    try:
        s = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    if "ProviderSetting" not in s:
        continue
    if re.search(r"class ProviderSetting\b", s):
        soft.append(sp)
        m = re.search(r"data class ProviderSetting\(", s)
        if m and cls is None:
            cls = (sp, s[m.start():m.start() + 4000])

if cls is None:
    print("::warning::data class ProviderSetting not found; candidates=" + ";".join(soft[:8]))
else:
    fields = sorted(set(re.findall(r"val (\w+)", cls[1])))
    print("::notice::ProviderSetting at " + cls[0])
    print("::notice::fields = " + ",".join(fields))
    missing = [f for f in ("name", "apiKey", "baseUrl") if f not in fields]
    if missing:
        print("::error::ProviderSetting missing " + ",".join(missing))
        raise SystemExit(1)

# --- 真正的改动 ---
t = (ROOT / P).read_text(encoding="utf-8")
if MARK in t:
    print("batch42: already applied")
    raise SystemExit(0)

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
                    provider.apiKey.contains(q, ignoreCase = true) ||
                    provider.baseUrl.contains(q, ignoreCase = true)
            }
        }
    }
'''
t = t.replace(A1, add1, 1)

for r in [
    MARK,
    "provider.apiKey.contains(q, ignoreCase = true)",
    "provider.baseUrl.contains(q, ignoreCase = true)",
    "val q = searchQuery.trim()",
]:
    if r not in t:
        fail("selfcheck missing " + repr(r))

(ROOT / P).write_text(t, encoding="utf-8")
print("batch42 v2: OK")