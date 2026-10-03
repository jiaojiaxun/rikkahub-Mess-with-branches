#!/usr/bin/env python3
'''batch42: 设置-供应商 搜索框支持搜 API Key 和 BaseUrl（原来只匹配供应商名）

用户澄清需求 12：设置-供应商页面的搜索框目前只能匹配 provider.name，
要改成也能匹配 apiKey 和 baseUrl。

前置校验：脚本先在 ai 模块定位 data class ProviderSetting，确认真的存在
name / apiKey / baseUrl 三个字段；不存在就 ::error 退出并打印实际字段名，
避免猜错字段名浪费一整轮构建。
'''
from pathlib import Path
import re

ROOT = Path.cwd()
P = "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingProviderPage.kt"
MARK = "rhProviderSearch"


def fail(msg):
    print('::error file=' + P + '::batch42 ' + msg[:1200])
    raise SystemExit(1)


# --- 前置校验：ProviderSetting 字段真实存在 ---
ps = None
for p in (ROOT / "ai").rglob("*.kt"):
    s = p.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"data class ProviderSetting\(", s)
    if m:
        ps = (p, s[m.start():m.start() + 3000])
        break

if ps is None:
    fail("cannot locate data class ProviderSetting in ai module")

body = ps[1]
fields = sorted(set(re.findall(r"val (\w+)", body)))
missing = [f for f in ("name", "apiKey", "baseUrl") if f not in fields]
if missing:
    print("::error::batch42 ProviderSetting missing fields: " + ",".join(missing))
    print("::notice::actual fields = " + ",".join(fields))
    raise SystemExit(1)

print("::notice::ProviderSetting verified, fields = " + ",".join(fields))

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

required = [
    MARK,
    "provider.apiKey.contains(q, ignoreCase = true)",
    "provider.baseUrl.contains(q, ignoreCase = true)",
    "val q = searchQuery.trim()",
]
for r in required:
    if r not in t:
        fail("selfcheck missing " + repr(r))

(ROOT / P).write_text(t, encoding="utf-8")
print("batch42: OK")