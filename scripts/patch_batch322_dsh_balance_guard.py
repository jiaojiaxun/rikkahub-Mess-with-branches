"""batch322 — balance card: only OpenAI-type providers expose a balance query.

ProviderBalanceText returns immediately unless the provider is
ProviderSetting.OpenAI with balanceOption.enabled, so the card would render as
an empty box for DeepSeek/other providers (the exact case in the reference
screenshot). Show the hint text unless the provider can actually report one.
"""

import os

ROOT = os.getcwd()
CHROME = os.path.join(
    ROOT,
    "app/src/main/java/me/rerere/rikkahub/ui/components/ai/RhDshChrome.kt",
)
DIAG = os.path.join(ROOT, "ci_diag_batch322_balance.txt")


def main():
    src = open(CHROME, "r", encoding="utf-8").read()
    before = (src.count('{') - src.count('}'), src.count('(') - src.count(')'))

    old = "                    if (provider != null) {\n                        ProviderBalanceText("
    new = (
        "                    if (provider is ProviderSetting.OpenAI && provider.balanceOption.enabled) {\n"
        "                        ProviderBalanceText("
    )
    count = src.count(old)
    info = "balance: anchor count=" + str(count) + " openai_guard=" + str("ProviderSetting.OpenAI" in src)
    print(info)

    if count != 1:
        print("::error title=rhDsh322::anchor count=" + str(count))
        open(DIAG, "w", encoding="utf-8").write(info + "\n")
        return

    src = src.replace(old, new)
    after = (src.count('{') - src.count('}'), src.count('(') - src.count(')'))
    if after != before:
        raise SystemExit("balance drift " + str(before) + " -> " + str(after))
    open(CHROME, "w", encoding="utf-8").write(src)
    print("::error title=rhDsh322::OK balance guard uses OpenAI + balanceOption")
    open(DIAG, "w", encoding="utf-8").write(info + "\n")


main()