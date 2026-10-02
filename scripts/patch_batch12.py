#!/usr/bin/env python3
"""Batch-12: "模型列表支持按提供商折叠，并会记住折叠状态".

`ColumnScope.ModelList` in ui/components/ai/ModelList.kt renders every provider as a
stickyHeader followed by that provider's models. With many providers configured the sheet is a
very long scroll, and there was no way to fold a provider away.

Design notes:

  * Collapse is implemented by feeding the provider an EMPTY model list rather than by wrapping
    the `items(...)` block in an `if`. Everything downstream already derives from those two maps
    (the initial-scroll `selectedModelPosition` math, the LazyRow badge positions, the LazyColumn
    itself), so one empty list keeps all of them consistent instead of leaving the scroll maths
    counting items that are no longer emitted.

  * Collapsing must NOT hide search results: while the search box has text every provider stays
    open, otherwise a match inside a collapsed provider would look like a bug.

  * Persistence goes to SharedPreferences through the existing readStringPreference /
    writeStringPreference helpers in ui/hooks/SharedPreferences.kt, so no field is added to the
    serialized Settings schema (and no migration is needed) for what is a pure view preference.
    Provider ids are stored as strings and compared as strings, so a malformed/legacy value can
    never crash on Uuid parsing.

  * The toggle is a text glyph rather than an icon: the file imports a fixed set of HugeIcons and
    has no rotation modifier imported, and "▾/▸" needs neither.

Anchored, idempotent, loud (::error + exit 1).
"""
import sys
from pathlib import Path

FAILURES = []
TARGET = Path("app/src/main/java/me/rerere/rikkahub/ui/components/ai/ModelList.kt")
MARKER = "rh-batch12"


def fail(msg):
    print(f"::error file={TARGET}::batch12 patch failed: {msg}", flush=True)
    FAILURES.append(msg)


def flatten(text):
    kept = []
    indexes = []
    for index, char in enumerate(text):
        if not char.isspace():
            kept.append(char)
            indexes.append(index)
    return "".join(kept), indexes


def match_flat(src, pattern):
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


IMPORT_ANDROID_OLD = "import androidx.compose.ui.platform.LocalHapticFeedback"

IMPORT_ANDROID_NEW = """import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback"""

IMPORT_HOOKS_OLD = "import me.rerere.rikkahub.ui.components.ui.icons.HeartIcon"

IMPORT_HOOKS_NEW = """import me.rerere.rikkahub.ui.components.ui.icons.HeartIcon
import me.rerere.rikkahub.ui.hooks.readStringPreference
import me.rerere.rikkahub.ui.hooks.writeStringPreference"""

CLASS_ANCHOR_OLD = "class ModelListState internal constructor("

CLASS_ANCHOR_NEW = '''/**
 * rh-batch12: collapse-by-provider - SharedPreferences key holding the comma-separated ids of
 * the providers the user folded away in the model picker.
 */
private const val COLLAPSED_PROVIDERS_PREF_KEY = "collapsedModelListProviders"

/** rh-batch12: tolerant decode - unknown/blank entries are dropped, never parsed as Uuid. */
private fun decodeCollapsedProviderIds(raw: String?): Set<String> =
    raw.orEmpty().split(',').map { it.trim() }.filter { it.isNotEmpty() }.toSet()

class ModelListState internal constructor('''

STATE_OLD = '''    var searchKeywords by remember { mutableStateOf("") }'''

STATE_NEW = '''    var searchKeywords by remember { mutableStateOf("") }

    // rh-batch12: collapse-by-provider, remembered across sessions. Stored in SharedPreferences
    // rather than Settings so a pure view preference needs no serialized-schema change.
    val localContext = LocalContext.current
    var collapsedProviderIds by remember {
        mutableStateOf(
            decodeCollapsedProviderIds(
                localContext.readStringPreference(COLLAPSED_PROVIDERS_PREF_KEY)
            )
        )
    }
    fun setProviderCollapsed(providerId: Uuid, collapsed: Boolean) {
        val id = providerId.toString()
        val next = if (collapsed) collapsedProviderIds + id else collapsedProviderIds - id
        collapsedProviderIds = next
        localContext.writeStringPreference(COLLAPSED_PROVIDERS_PREF_KEY, next.joinToString(","))
    }'''

TYPE_MAP_OLD = '''    val typeFilteredModelsByProvider = remember(providers, modelType) {
        providers.associate { provider ->
            provider.id to provider.models.fastFilter { it.matchesPickerType(modelType) }
        }
    }'''

TYPE_MAP_NEW = '''    val typeFilteredModelsByProvider = remember(providers, modelType, collapsedProviderIds) {
        providers.associate { provider ->
            // rh-batch12: a folded provider contributes no models, so the initial-scroll maths
            // below and the emitted list stay in agreement.
            provider.id to provider.models.fastFilter { it.matchesPickerType(modelType) }
                .let { if (provider.id.toString() in collapsedProviderIds) emptyList() else it }
        }
    }'''

SEARCH_MAP_OLD = '''    val searchFilteredModelsByProvider = remember(providers, modelType, searchKeywords) {
        providers.associate { provider ->
            provider.id to provider.models.fastFilter {
                it.matchesPickerType(modelType) && it.displayName.contains(searchKeywords, true)
            }
        }
    }'''

SEARCH_MAP_NEW = '''    val searchFilteredModelsByProvider =
        remember(providers, modelType, searchKeywords, collapsedProviderIds) {
            providers.associate { provider ->
                // rh-batch12: hiding a match while the user is actively searching would read as a
                // bug, so folding only takes effect while the search box is empty.
                val folded =
                    provider.id.toString() in collapsedProviderIds && searchKeywords.isBlank()
                provider.id to provider.models.fastFilter {
                    it.matchesPickerType(modelType) && it.displayName.contains(searchKeywords, true)
                }.let { if (folded) emptyList() else it }
            }
        }'''

HEADER_OLD = '''                    Spacer(modifier = Modifier.weight(1f))

                    ProviderBalanceText(
                        providerSetting = providerSetting,
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
            }'''

HEADER_NEW = '''                    Spacer(modifier = Modifier.weight(1f))

                    ProviderBalanceText(
                        providerSetting = providerSetting,
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary,
                    )

                    // rh-batch12: per-provider fold toggle. Text glyphs instead of an icon, so no
                    // new HugeIcons import and no rotation modifier are required.
                    IconButton(
                        onClick = {
                            setProviderCollapsed(
                                providerSetting.id,
                                providerSetting.id.toString() !in collapsedProviderIds,
                            )
                        },
                        modifier = Modifier.size(24.dp),
                    ) {
                        Text(
                            text = if (providerSetting.id.toString() in collapsedProviderIds) "\\u25b8" else "\\u25be",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.primary,
                        )
                    }
                }
            }'''


def main():
    if not TARGET.exists():
        fail("file not found")
        print("batch12 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
        return 1
    src = TARGET.read_text(encoding="utf-8")
    if MARKER in src:
        print("already patched: " + str(TARGET), flush=True)
        return 0
    original = src

    for old, new, label in (
        (IMPORT_ANDROID_OLD, IMPORT_ANDROID_NEW, "LocalContext import"),
        (IMPORT_HOOKS_OLD, IMPORT_HOOKS_NEW, "preference helper imports"),
        (CLASS_ANCHOR_OLD, CLASS_ANCHOR_NEW, "pref key + decoder"),
        (STATE_OLD, STATE_NEW, "collapse state"),
        (TYPE_MAP_OLD, TYPE_MAP_NEW, "type map respects fold"),
        (SEARCH_MAP_OLD, SEARCH_MAP_NEW, "search map respects fold"),
        (HEADER_OLD, HEADER_NEW, "header toggle"),
    ):
        src = replace_once(src, old, new, label)
        if src is None:
            print("batch12 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
            return 1

    if src == original or MARKER not in src:
        fail("nothing changed")
        print("batch12 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
        return 1

    TARGET.write_text(src, encoding="utf-8")
    print("patched: " + str(TARGET), flush=True)
    print("batch12 patches applied", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
