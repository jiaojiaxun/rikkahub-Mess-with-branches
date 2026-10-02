from pathlib import Path

ROOT = Path.cwd()


def patch(path: str, replacements: list[tuple[str, str]]) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    for old, new in replacements:
        count = text.count(old)
        if count != 1:
            raise SystemExit(f"{path}: expected one anchor, found {count}: {old[:100]!r}")
        text = text.replace(old, new, 1)
    target.write_text(text, encoding="utf-8")


patch(
    "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingSearchPage.kt",
    [
        (
            "    var duplicateProviderName by remember { mutableStateOf<String?>(null) }\n",
            "    var duplicateProviderName by remember { mutableStateOf<String?>(null) }\n"
            "    var pendingDuplicateOptions by remember { mutableStateOf<SearchServiceOptions?>(null) }\n",
        ),
        (
            "                if (duplicate != null) {\n                    duplicateProviderName = settings.searchServices\n                        .firstOrNull { it.id == duplicate }?.displayName\n                } else {",
            "                if (duplicate != null) {\n                    pendingDuplicateOptions = options\n                    duplicateProviderName = settings.searchServices\n                        .firstOrNull { it.id == duplicate }?.displayName\n                } else {",
        ),
        (
            "            onDismissRequest = { duplicateProviderName = null },\n            title = { Text(stringResource(R.string.search_duplicate_key_title)) },",
            "            onDismissRequest = {\n                duplicateProviderName = null\n                pendingDuplicateOptions = null\n            },\n            title = { Text(stringResource(R.string.search_duplicate_key_title)) },",
        ),
        (
            "                TextButton(onClick = { duplicateProviderName = null }) {\n                    Text(stringResource(R.string.confirm))\n                }",
            "                TextButton(onClick = {\n                    pendingDuplicateOptions?.let { options ->\n                        vm.updateSettings(\n                            settings.copy(searchServices = listOf(options) + settings.searchServices)\n                        )\n                        scope.launch { lazyListState.animateScrollToItem(0) }\n                    }\n                    duplicateProviderName = null\n                    pendingDuplicateOptions = null\n                    showAddDialog = false\n                }) {\n                    Text(stringResource(R.string.search_duplicate_key_continue))\n                }",
        ),
        (
            "                TextButton(onClick = { duplicateProviderName = null }) {\n                    Text(stringResource(R.string.cancel))\n                }",
            "                TextButton(onClick = {\n                    duplicateProviderName = null\n                    pendingDuplicateOptions = null\n                }) {\n                    Text(stringResource(R.string.cancel))\n                }",
        ),
    ],
)

patch(
    "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingSearchDetailPage.kt",
    [
        (
            "    var duplicateProviderName by remember { mutableStateOf<String?>(null) }\n",
            "    var duplicateProviderName by remember { mutableStateOf<String?>(null) }\n"
            "    var pendingDuplicateOptions by remember { mutableStateOf<SearchServiceOptions?>(null) }\n",
        ),
        (
            "        if (duplicate != null) {\n            duplicateProviderName = settings.searchServices\n                .firstOrNull { it.id == duplicate }?.displayName\n        } else {",
            "        if (duplicate != null) {\n            pendingDuplicateOptions = updated\n            duplicateProviderName = settings.searchServices\n                .firstOrNull { it.id == duplicate }?.displayName\n        } else {",
        ),
        (
            "            onDismissRequest = { duplicateProviderName = null },\n            title = { Text(stringResource(R.string.search_duplicate_key_title)) },",
            "            onDismissRequest = {\n                duplicateProviderName = null\n                pendingDuplicateOptions = null\n            },\n            title = { Text(stringResource(R.string.search_duplicate_key_title)) },",
        ),
        (
            "                    duplicateProviderName = null\n                    persist(options)\n                }) { Text(stringResource(R.string.search_duplicate_key_continue)) }",
            "                    pendingDuplicateOptions?.let(::persist)\n                    duplicateProviderName = null\n                    pendingDuplicateOptions = null\n                }) { Text(stringResource(R.string.search_duplicate_key_continue)) }",
        ),
        (
            "                TextButton(onClick = { duplicateProviderName = null }) {\n                    Text(stringResource(R.string.cancel))\n                }",
            "                TextButton(onClick = {\n                    duplicateProviderName = null\n                    pendingDuplicateOptions = null\n                }) {\n                    Text(stringResource(R.string.cancel))\n                }",
        ),
    ],
)

print("batch17 pending duplicate-key candidates wired")
