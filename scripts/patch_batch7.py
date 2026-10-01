#!/usr/bin/env python3
"""Batch-7: fetch a provider's model catalog once.

Why: ModelList keyed produceState() on the whole ProviderSetting object, so every
add/delete/reorder of a model re-keyed it and re-issued listModels() over the network.
The fetch now keys on (id, baseUrl, apiKey) and reads/writes SettingVM's catalog cache.

Convention matches the other batches: anchored, idempotent, loud (::error + exit 1).
Anchors are whitespace-tolerant: the upstream sources wrap parameters across several
lines, which is what broke run #43.
"""
import re
import sys
from pathlib import Path

FAILURES = []
TARGET = "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingProviderDetailPage.kt"
MARKER = "rh-batch7:fetch-once"


def fail(msg):
    print(f"::error file={TARGET}::batch7 patch failed: {msg}", flush=True)
    FAILURES.append(msg)


def tolerant(text):
    """Regex for `text` where every whitespace run matches any (possibly empty) whitespace."""
    parts = re.split(r"\s+", text.strip())
    return r"\s*".join(re.escape(p) for p in parts)


def replace_once(src, pattern, replacement, label):
    pat = re.compile(tolerant(pattern))
    matches = list(pat.finditer(src))
    if len(matches) != 1:
        fail(f"{label}: expected 1 match, found {len(matches)}")
        return None
    m = matches[0]
    return src[: m.start()] + replacement + src[m.end():]


HELPER_AND_PAGE = """    /** Stable identity of the endpoint a model catalog was fetched from. */
    private fun ProviderSetting.modelCatalogKey(): String = when (this) {
        is ProviderSetting.OpenAI -> "$id|$baseUrl|$apiKey"
        is ProviderSetting.Google -> "$id|$baseUrl|$apiKey"
        is ProviderSetting.Claude -> "$id|$baseUrl|$apiKey"
        else -> id.toString()
    }

    @Composable
    private fun SettingProviderModelPage(
        provider: ProviderSetting,
        onEdit: (ProviderSetting) -> Unit,
        vm: SettingVM = koinViewModel(),
    ) {
        val providerManager = koinInject<ProviderManager>()
        ModelList(
            providerSetting = provider,
            onUpdateProvider = onEdit,
            // rh-batch7:fetch-once - at most one listModels() per (id, baseUrl, apiKey).
            fetchModels = {
                val key = provider.modelCatalogKey()
                vm.cachedModelCatalog(key) ?: providerManager
                    .getProviderByType(provider)
                    .listModels(provider)
                    .also { vm.putModelCatalog(key, it) }
            },
            onFetchFailed = { vm.clearModelCatalog(provider.modelCatalogKey()) },
        )
    }"""

PAGE_OLD = """@Composable private fun SettingProviderModelPage(provider: ProviderSetting, onEdit: (ProviderSetting) -> Unit) {
    ModelList(providerSetting = provider, onUpdateProvider = onEdit)
}"""

MODEL_LIST_HEAD_OLD = """@Composable private fun ModelList(providerSetting: ProviderSetting, onUpdateProvider: (ProviderSetting) -> Unit) {
    val providerManager = koinInject<ProviderManager>()
    val toaster = LocalToaster.current
    val modelLoad by produceState(ModelListLoadState(), providerSetting) {"""

MODEL_LIST_HEAD_NEW = """@Composable
    private fun ModelList(
        providerSetting: ProviderSetting,
        onUpdateProvider: (ProviderSetting) -> Unit,
        fetchModels: suspend () -> List<Model>,
        onFetchFailed: () -> Unit = {},
    ) {
        val toaster = LocalToaster.current
        // rh-batch7:fetch-once - re-key on endpoint identity, NOT on the provider object:
        // add/delete/reorder only changes provider.models, which must not restart the fetch.
        val fetchKey = remember(providerSetting) { providerSetting.modelCatalogKey() }
        val modelLoad by produceState(ModelListLoadState(), fetchKey) {"""

FETCH_OLD = """value = ModelListLoadState(phase = 2)
                val fetched = providerManager.getProviderByType(providerSetting)
                    .listModels(providerSetting)"""

FETCH_NEW = """value = ModelListLoadState(phase = 2)
                val fetched = fetchModels()"""

FAILURE_OLD = "value = ModelListLoadState(phase = 5, failed = true)"

FAILURE_NEW = """value = ModelListLoadState(phase = 5, failed = true)
                onFetchFailed()"""


def main():
    path = Path(TARGET)
    if not path.exists():
        fail("file not found")
        print("batch7 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
        return 1
    src = path.read_text(encoding="utf-8")
    if MARKER in src:
        print("already patched: " + TARGET, flush=True)
        return 0
    original = src

    for old, new, label in (
        (PAGE_OLD, HELPER_AND_PAGE, "SettingProviderModelPage"),
        (MODEL_LIST_HEAD_OLD, MODEL_LIST_HEAD_NEW, "ModelList head"),
        (FETCH_OLD, FETCH_NEW, "listModels call"),
        (FAILURE_OLD, FAILURE_NEW, "failure branch"),
    ):
        src = replace_once(src, old, new, label)
        if src is None:
            print("batch7 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
            return 1

    if src == original or MARKER not in src:
        fail("marker missing after patching")
        print("batch7 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
        return 1
    path.write_text(src, encoding="utf-8")
    print("patched: " + TARGET, flush=True)
    print("batch7 patches applied", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
