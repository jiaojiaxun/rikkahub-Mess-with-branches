"""batch321 — run#560 compile error: Unresolved reference 'apiKey' on ProviderSetting.

ProviderSetting is a sealed base type; apiKey only exists on some concrete
providers, so the balance card must not read it. Keep the余额 card for any
provider (ProviderBalanceText already renders only when the provider supports
balance queries) and keep the hint when there is no provider at all.
"""

import os

ROOT = os.getcwd()
CHROME = os.path.join(
    ROOT,
    "app/src/main/java/me/rerere/rikkahub/ui/components/ai/RhDshChrome.kt",
)
DIAG = os.path.join(ROOT, "ci_diag_batch321_apikey.txt")


def main():
    src = open(CHROME, "r", encoding="utf-8").read()
    before = (src.count('{') - src.count('}'), src.count('(') - src.count(')'))

    old = (
        "                    if (provider != null && provider.apiKey.isNotBlank()) {\n"
        "                        ProviderBalanceText(\n"
        "                            providerSetting = provider,\n"
        "                            style = MaterialTheme.typography.bodyMedium,\n"
        "                            color = scheme.onSurface,\n"
        "                        )\n"
        "                    } else {\n"
        "                        Text(\"填写 API Key 后可查询余额\", fontSize = 14.sp, color = scheme.onSurfaceVariant)\n"
        "                    }"
    )
    new = (
        "                    if (provider != null) {\n"
        "                        ProviderBalanceText(\n"
        "                            providerSetting = provider,\n"
        "                            style = MaterialTheme.typography.bodyMedium,\n"
        "                            color = scheme.onSurface,\n"
        "                        )\n"
        "                    } else {\n"
        "                        Text(\"填写 API Key 后可查询余额\", fontSize = 14.sp, color = scheme.onSurfaceVariant)\n"
        "                    }"
    )

    count = src.count(old)
    info = "apikey: anchor count=" + str(count)
    print(info)

    if count == 1:
        src = src.replace(old, new)
        after = (src.count('{') - src.count('}'), src.count('(') - src.count(')'))
        if after != before:
            raise SystemExit("balance drift " + str(before) + " -> " + str(after))
        if "provider.apiKey" in src:
            raise SystemExit("apiKey still referenced")
        open(CHROME, "w", encoding="utf-8").write(src)
        print("::error title=rhDsh321::OK balance card no longer reads apiKey")
    else:
        print("::error title=rhDsh321::anchor count=" + str(count))

    open(DIAG, "w", encoding="utf-8").write(info + "\n")


main()