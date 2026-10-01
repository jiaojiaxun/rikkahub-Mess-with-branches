#!/usr/bin/env python3
"""Batch-7: fetch a provider's model catalog once.

Why: ModelList keyed produceState() on the whole ProviderSetting object, so every
add/delete/reorder of a model re-keyed it and re-issued listModels() over the network.
The fetch now keys on (id, baseUrl, apiKey) and reads/writes SettingVM's catalog cache.

Anchors are matched with ALL whitespace removed from both sides (see match_flat), because
reflowing the upstream file - e.g. a newline between `Unit` and `)` - broke two earlier
versions of this script even though the code was unchanged.

Convention matches the other batches: anchored, idempotent, loud (::error + exit 1).
"""
import sys
from pathlib import Path

FAILURES = []
TARGET = "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingProviderDetailPage.kt"
MARKER = "rh-batch7:fetch-once"


def fail(msg):
    print(f"::error file={TARGET}::batch7 patch failed: {msg}", flush=True)
    FAILURES.append(msg)


def flatten(text):
    """Return (text_without_whitespace, original_index_of_each_kept_char)."""
    kept = []
    indexes = []
    for index, char in enumerate(text):
        if not char.isspace():
            kept.append(char)
            indexes.append(index)
    return "".join(kept), indexes


def match_flat(src, pattern):
    """Locate `pattern` in `src`, ignoring all whitespace. Returns (start, end) or None."""
    flat_src, indexes = flatten(src)
    flat_pattern, _ = flatten(pattern)
    if not flat_pattern:
        return None
    positions = flat_src.count(flat_pattern)
    if positions != 1:
        return ("count", positions)
    start_flat = flat_src.find(flat_pattern)
    end_flat = start_flat + len(flat_pattern) - 1
    return (indexes[start_flat], indexes[end_flat] + 1)


def replace_once(src, pattern, replacement, label):
    found = match_flat(src, pattern)
    if found is None:
        fail(f"{label}: empty anchor")
        return None
    if isinstance(found[0], str):
        fail(f"{label}: expected 1 match, found {found[1]}")
        return None
    start, end = found
    return src[:start] + replacement + src[end:]


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

PAGE_OLD = """@Composable
private fun SettingProviderModelPage(provider: ProviderSetting, onEdit: (ProviderSetting) -> Unit) {
    ModelList(providerSetting = provider, onUpdateProvider = onEdit)
}"""

MODEL_LIST_HEAD_OLD = """@Composable
private fun ModelList(providerSetting: ProviderSetting, onUpdateProvider: (ProviderSetting) -> Unit) {
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
        (FAILURE_OLD, FAILURE_NEW, "failure branch"),
        (FETCH_OLD, FETCH_NEW, "listModels call"),
        (MODEL_LIST_HEAD_OLD, MODEL_LIST_HEAD_NEW, "ModelList head"),
        (PAGE_OLD, HELPER_AND_PAGE, "SettingProviderModelPage"),
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
