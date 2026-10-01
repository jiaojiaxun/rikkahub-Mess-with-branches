#!/usr/bin/env python3
"""Batch-7: fetch a provider's model catalog once.

The ModelList produceState was keyed on the whole ProviderSetting object, so adding or
removing a model re-keyed it and re-issued listModels() over the network. The fetch now
keys on a stable provider key (id + baseUrl + apiKey) and reads/writes SettingVM's cache.

Convention matches the other batches: anchored, idempotent, loud (::error + exit 1).
"""
import re
import sys
from pathlib import Path

FAILURES = []
TARGET = "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingProviderDetailPage.kt"
MARKER = "rh-batch7:fetch-once"


def fail(path, msg):
    print(f"::error file={path}::batch7 patch failed: {msg}", flush=True)
    FAILURES.append(f"{path}: {msg}")


def t_model_list(src):
    if MARKER in src:
        return src
    # Anchor: the old page composable + produceState keyed on providerSetting.
    pat = re.compile(
        r"@Composable\s+private fun SettingProviderModelPage\(provider: ProviderSetting, onEdit: \(ProviderSetting\) -> Unit\) \{\s*"
        r"ModelList\(providerSetting = provider, onUpdateProvider = onEdit\)\s*\}"
    )
    ms = list(pat.finditer(src))
    if len(ms) != 1:
        fail(TARGET, "SettingProviderModelPage anchor not found")
        return None
    new_page = (
        "@Composable\n"
        "    private fun SettingProviderModelPage(\n"
        "        provider: ProviderSetting,\n"
        "        onEdit: (ProviderSetting) -> Unit,\n"
        "        vm: SettingVM = koinViewModel(),\n"
        "    ) {\n"
        "        ModelList(\n"
        "            providerSetting = provider,\n"
        "            onUpdateProvider = onEdit,\n"
        "            // rh-batch7:fetch-once - one listModels() per (id, baseUrl, apiKey).\n"
        "            // Model add/remove/edit keeps the cached catalog, so editing models\n"
        "            // never re-requests the provider's model list.\n"
        "            fetchModels = {\n"
        "                val key = provider.modelCatalogKey()\n"
        "                vm.cachedModelCatalog(key) ?: providerManager\n"
        "                    .getProviderByType(provider)\n"
        "                    .listModels(provider)\n"
        "                    .also { vm.putModelCatalog(key, it) }\n"
        "            },\n"
        "            onFetchFailed = { vm.clearModelCatalog(provider.modelCatalogKey()) },\n"
        "        )\n"
        "    }"
    )
    src = src[: ms[0].start()] + new_page + src[ms[0].end() :]

    # Anchor: produceState keyed on the whole providerSetting object.
    pat2 = re.compile(
        r"fun ModelList\(\s*providerSetting: ProviderSetting,\s*onUpdateProvider: \(ProviderSetting\) -> Unit\s*\) \{\s*"
        r"val providerManager = koinInject<ProviderManager>\(\)\s*"
        r"val toaster = LocalToaster.current\s*"
        r"val modelLoad by produceState\(ModelListLoadState\(\), providerSetting\) \{"
    )
    ms2 = list(pat2.finditer(src))
    if len(ms2) != 1:
        fail(TARGET, "ModelList produceState anchor not found")
        return None
    new_head = (
        "fun ModelList(\n"
        "        providerSetting: ProviderSetting,\n"
        "        onUpdateProvider: (ProviderSetting) -> Unit,\n"
        "        fetchModels: suspend () -> List<Model>,\n"
        "        onFetchFailed: () -> Unit = {},\n"
        "    ) {\n"
        "        val toaster = LocalToaster.current\n"
        "        // rh-batch7:fetch-once - re-key on endpoint identity, NOT on the provider\n"
        "        // object: add/delete/reorder only changes provider.models, which must not\n"
        "        // restart the network fetch.\n"
        "        val fetchKey = remember(providerSetting) {\n"
        "            providerSetting.modelCatalogKey()\n"
        "        }\n"
        "        val modelLoad by produceState(ModelListLoadState(), fetchKey) {"
    )
    src = src[: ms2[0].start()] + new_head + src[ms2[0].end() :]

    # Fetch through the callback; mark failures for cache invalidation.
    pat3 = re.compile(
        r"value = ModelListLoadState\(phase = 2\)\s*"
        r"val fetched = providerManager\.getProviderByType\(providerSetting\)\s*"
        r"\.listModels\(providerSetting\)"
    )
    ms3 = list(pat3.finditer(src))
    if len(ms3) != 1:
        fail(TARGET, "listModels call anchor not found")
        return None
    src = src[: ms3[0].start()] + "value = ModelListLoadState(phase = 2)\n                val fetched = fetchModels()" + src[ms3[0].end() :]

    pat4 = re.compile(
        r"value = ModelListLoadState\(phase = 5, failed = true\)"
    )
    ms4 = list(pat4.finditer(src))
    if len(ms4) != 1:
        fail(TARGET, "failure branch anchor not found")
        return None
    src = src[: ms4[0].start()] + "value = ModelListLoadState(phase = 5, failed = true)\n                onFetchFailed()" + src[ms4[0].end() :]

    # Stable-key helper for providers whose listModels depends on endpoint + key.
    helper = (
        "\n    private fun ProviderSetting.modelCatalogKey(): String = when (this) {\n"
        "        is ProviderSetting.OpenAI -> \"$id|$baseUrl|$apiKey\"\n"
        "        is ProviderSetting.Google -> \"$id|$baseUrl|$apiKey\"\n"
        "        is ProviderSetting.Claude -> \"$id|$baseUrl|$apiKey\"\n"
        "        else -> id.toString()\n"
        "    }\n"
    )
    anchor = "    @Composable\n    private fun SettingProviderModelPage"
    idx = src.find(anchor)
    if idx < 0:
        fail(TARGET, "helper insertion anchor not found")
        return None
    src = src[:idx] + helper.lstrip("\n") + "\n" + src[idx:]
    return src


def main():
    p = Path(TARGET)
    if not p.exists():
        fail(TARGET, "file not found")
    else:
        out = t_model_list(p.read_text(encoding="utf-8"))
        if out:
            p.write_text(out, encoding="utf-8")
            print("patched: " + TARGET, flush=True)
    if FAILURES:
        print("batch7 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
        return 1
    print("batch7 patches applied", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
