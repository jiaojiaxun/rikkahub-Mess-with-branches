from pathlib import Path

ROOT = Path.cwd()


def patch(path: str, replacements: list[tuple[str, str]]) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    for old, new in replacements:
        count = text.count(old)
        if count != 1:
            raise SystemExit(f"{path}: expected one anchor, found {count}: {old[:80]!r}")
        text = text.replace(old, new, 1)
    target.write_text(text, encoding="utf-8")


patch(
    "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingSearchPage.kt",
    [
        (
            "    var showAddDialog by remember { mutableStateOf(false) }\n",
            "    var showAddDialog by remember { mutableStateOf(false) }\n"
            "    var duplicateProviderName by remember { mutableStateOf<String?>(null) }\n",
        ),
        (
            "            onConfirm = { options ->\n                showAddDialog = false\n                vm.updateSettings(\n                    settings.copy(\n                        searchServices = listOf(options) + settings.searchServices\n                    )\n                )\n                scope.launch {\n                    lazyListState.animateScrollToItem(0)\n                }\n            }\n",
            "            onConfirm = { options ->\n                val duplicate = findDuplicateSearchApiKey(options, settings.searchServices)\n                if (duplicate != null) {\n                    duplicateProviderName = settings.searchServices\n                        .firstOrNull { it.id == duplicate }?.displayName\n                } else {\n                    showAddDialog = false\n                    vm.updateSettings(\n                        settings.copy(\n                            searchServices = listOf(options) + settings.searchServices\n                        )\n                    )\n                    scope.launch {\n                        lazyListState.animateScrollToItem(0)\n                    }\n                }\n            }\n",
        ),
        (
            "    if (showAddDialog) {\n",
            "    duplicateProviderName?.let { providerName ->\n        AlertDialog(\n            onDismissRequest = { duplicateProviderName = null },\n            title = { Text(stringResource(R.string.search_duplicate_key_title)) },\n            text = {\n                Text(stringResource(R.string.search_duplicate_key_message, providerName))\n            },\n            confirmButton = {\n                TextButton(onClick = { duplicateProviderName = null }) {\n                    Text(stringResource(R.string.confirm))\n                }\n            },\n            dismissButton = {\n                TextButton(onClick = { duplicateProviderName = null }) {\n                    Text(stringResource(R.string.cancel))\n                }\n            },\n        )\n    }\n\n    if (showAddDialog) {\n",
        ),
    ],
)

patch(
    "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingSearchDetailPage.kt",
    [
        (
            "import androidx.compose.material3.Card\n",
            "import androidx.compose.material3.AlertDialog\nimport androidx.compose.material3.Card\n",
        ),
        (
            "import androidx.compose.material3.Text\n",
            "import androidx.compose.material3.Text\nimport androidx.compose.material3.TextButton\n",
        ),
        (
            "    var options by remember(service) { mutableStateOf(service) }\n\n    fun save(updated: SearchServiceOptions) {\n        options = updated\n        val newServices = settings.searchServices.toMutableList()\n        newServices[serviceIndex] = updated\n        vm.updateSettings(settings.copy(searchServices = newServices))\n    }\n",
            "    var options by remember(service) { mutableStateOf(service) }\n    var duplicateProviderName by remember { mutableStateOf<String?>(null) }\n\n    fun persist(updated: SearchServiceOptions) {\n        options = updated\n        val newServices = settings.searchServices.toMutableList()\n        newServices[serviceIndex] = updated\n        vm.updateSettings(settings.copy(searchServices = newServices))\n    }\n\n    fun save(updated: SearchServiceOptions) {\n        val duplicate = findDuplicateSearchApiKey(updated, settings.searchServices)\n        if (duplicate != null) {\n            duplicateProviderName = settings.searchServices\n                .firstOrNull { it.id == duplicate }?.displayName\n        } else {\n            persist(updated)\n        }\n    }\n",
        ),
        (
            "    ) { padding ->\n",
            "    ) { padding ->\n",
        ),
        (
            "    }\n}\n\n@Suppress(\"UNCHECKED_CAST\")\n",
            "    }\n\n    duplicateProviderName?.let { providerName ->\n        AlertDialog(\n            onDismissRequest = { duplicateProviderName = null },\n            title = { Text(stringResource(R.string.search_duplicate_key_title)) },\n            text = { Text(stringResource(R.string.search_duplicate_key_message, providerName)) },\n            confirmButton = {\n                TextButton(onClick = {\n                    duplicateProviderName = null\n                    persist(options)\n                }) { Text(stringResource(R.string.search_duplicate_key_continue)) }\n            },\n            dismissButton = {\n                TextButton(onClick = { duplicateProviderName = null }) {\n                    Text(stringResource(R.string.cancel))\n                }\n            },\n        )\n    }\n}\n\n@Suppress(\"UNCHECKED_CAST\")\n",
        ),
    ],
)

strings = ROOT / "app/src/main/res/values/strings.xml"
text = strings.read_text(encoding="utf-8")
anchor = "</resources>"
addition = (
    "  <string name=\"search_duplicate_key_title\">Duplicate API key</string>\n"
    "  <string name=\"search_duplicate_key_message\">This API key is already configured for %s. The key itself is hidden.</string>\n"
    "  <string name=\"search_duplicate_key_continue\">Save anyway</string>\n"
)
if text.count(anchor) != 1:
    raise SystemExit("strings.xml: missing unique resources anchor")
if "search_duplicate_key_title" not in text:
    text = text.replace(anchor, addition + anchor, 1)
    strings.write_text(text, encoding="utf-8")

print("batch16 search duplicate-key warning applied")
