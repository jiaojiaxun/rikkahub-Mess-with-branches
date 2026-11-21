package me.rerere.rikkahub.ui.pages.setting

import me.rerere.hugeicons.HugeIcons
import me.rerere.rikkahub.ui.pages.setting.components.ProviderRequirement
import me.rerere.hugeicons.stroke.DragDropHorizontal
import me.rerere.hugeicons.stroke.Add01
import me.rerere.hugeicons.stroke.Search01
import me.rerere.hugeicons.stroke.Cancel01
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LargeFlexibleTopAppBar
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.ProvideTextStyle
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.scale
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.dokar.sonner.ToastType
import me.rerere.ai.provider.ProviderSetting
import me.rerere.rikkahub.R
import me.rerere.rikkahub.Screen
import me.rerere.rikkahub.ui.components.nav.BackButton
import me.rerere.rikkahub.ui.components.ui.AutoAIIcon
import me.rerere.rikkahub.ui.components.ui.Tag
import me.rerere.rikkahub.ui.components.ui.TagType
import me.rerere.rikkahub.ui.context.LocalNavController
import me.rerere.rikkahub.ui.context.LocalToaster
import me.rerere.rikkahub.ui.hooks.useEditState
import me.rerere.rikkahub.ui.pages.setting.components.ProviderConfigure
import me.rerere.rikkahub.ui.theme.CustomColors
import me.rerere.rikkahub.utils.plus
import org.koin.androidx.compose.koinViewModel
import sh.calvin.reorderable.ReorderableItem
import sh.calvin.reorderable.rememberReorderableLazyListState
import kotlin.uuid.Uuid

// rhProviderSearch: ProviderSetting 是 sealed class，apiKey/baseUrl 只挂在各子类上，
// 这里按实际子类提取，避免对不存在的字段做引用。
private fun providerSearchExtra(provider: ProviderSetting): String =
    when (provider) {
        is ProviderSetting.OpenAI -> provider.apiKey + " " + provider.baseUrl
        is ProviderSetting.Google -> provider.apiKey + " " + provider.baseUrl
        is ProviderSetting.Claude -> provider.apiKey + " " + provider.baseUrl
        else -> ""
    }

@Composable
fun SettingProviderPage(vm: SettingVM = koinViewModel()) {
    val settings by vm.settings.collectAsStateWithLifecycle()
    val navController = LocalNavController.current
    val scrollBehavior = TopAppBarDefaults.exitUntilCollapsedScrollBehavior()
    var searchQuery by remember { mutableStateOf("") }
    val lazyListState = rememberLazyListState()
    var providerToDelete by remember { mutableStateOf<ProviderSetting?>(null) }

    // rhKeyMerge: 新建供应商时自动查重,相同 URL 或 API Key 命中时询问是否合并
    var pendingProviderMerge by remember { mutableStateOf<Pair<ProviderSetting, ProviderSetting>?>(null) }
    val rhAddOrMergeProvider: (ProviderSetting) -> Unit = { rhCandidate ->
        val rhDuplicate = rhFindDuplicateProvider(rhCandidate, settings.providers)
        if (rhDuplicate != null) {
            pendingProviderMerge = rhCandidate to rhDuplicate
        } else {
            vm.updateSettings(settings.copy(providers = listOf(rhCandidate) + settings.providers))
        }
    }
    val reorderableState = rememberReorderableLazyListState(lazyListState) { from, to ->
        val newProviders = settings.providers.toMutableList().apply {
            add(to.index, removeAt(from.index))
        }
        vm.updateSettings(settings.copy(providers = newProviders))
    }

    // rhProviderSearch: 搜索框同时匹配 供应商名 / API Key / BaseUrl
    val filteredProviders = remember(settings.providers, searchQuery) {
        if (searchQuery.isBlank()) {
            settings.providers
        } else {
            val q = searchQuery.trim()
            settings.providers.filter { provider ->
                provider.name.contains(q, ignoreCase = true) ||
                    providerSearchExtra(provider).contains(q, ignoreCase = true)
            }
        }
    }

    Scaffold(
        topBar = {
            LargeFlexibleTopAppBar(
                title = {
                    Text(text = stringResource(R.string.setting_provider_page_title))
                },
                navigationIcon = {
                    BackButton()
                },
                actions = {
                    // rhProviderTidy: 一键整理 —— 启用的在上,组内按最后调用时间降序,无记录的保持原顺序
                    IconButton(
                        onClick = {
                            val order = settings.providers.withIndex().associate { it.value.id to it.index }
                            val used = settings.providerLastUsedAt
                            val sorted = settings.providers.sortedWith(
                                compareByDescending<ProviderSetting> { it.enabled }
                                    .thenByDescending { used[it.id] ?: Long.MIN_VALUE }
                                    .thenBy { order[it.id] ?: Int.MAX_VALUE }
                            )
                            vm.updateSettings(settings.copy(providers = sorted))
                        }
                    ) {
                        Icon(HugeIcons.DragDropHorizontal, contentDescription = stringResource(R.string.setting_provider_page_tidy))
                    }
                    AddButton {
                        rhAddOrMergeProvider(it)
                    }
                },
                scrollBehavior = scrollBehavior,
                colors = CustomColors.topBarColors
            )
        },
        modifier = Modifier.nestedScroll(scrollBehavior.nestedScrollConnection),
        containerColor = CustomColors.topBarColors.containerColor,
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(top = innerPadding.calculateTopPadding())
        ) {
            // Search bar
            OutlinedTextField(
                value = searchQuery,
                onValueChange = { searchQuery = it },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                placeholder = { Text(stringResource(R.string.setting_provider_page_search_providers)) },
                leadingIcon = {
                    Icon(HugeIcons.Search01, contentDescription = null)
                },
                trailingIcon = {
                    if (searchQuery.isNotEmpty()) {
                        IconButton(onClick = { searchQuery = "" }) {
                            Icon(HugeIcons.Cancel01, contentDescription = stringResource(R.string.accessibility_clear_text))
                        }
                    }
                },
                singleLine = true,
                shape = CircleShape,
            )


            LazyColumn(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f)
                    .imePadding(),
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp) +
                    PaddingValues(bottom = innerPadding.calculateBottomPadding()),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                state = lazyListState,
            ) {
                items(filteredProviders, key = { it.id }) { provider ->
                    ReorderableItem(
                        state = reorderableState,
                        key = provider.id
                    ) { isDragging ->
                        ProviderItem(
                            modifier = Modifier
                                .scale(if (isDragging) 0.95f else 1f)
                                .fillMaxWidth(),
                            provider = provider,
                            dragHandle = {
                                val haptic = LocalHapticFeedback.current
                                IconButton(
                                    onClick = {},
                                    modifier = Modifier
                                        .longPressDraggableHandle(
                                            onDragStarted = {
                                                haptic.performHapticFeedback(HapticFeedbackType.GestureThresholdActivate)
                                            },
                                            onDragStopped = {
                                                haptic.performHapticFeedback(HapticFeedbackType.GestureEnd)
                                            }
                                        )
                                ) {
                                    Icon(
                                        imageVector = HugeIcons.DragDropHorizontal,
                                        contentDescription = null
                                    )
                                }
                            },
                            onClick = {
                                navController.navigate(Screen.SettingProviderDetail(providerId = provider.id.toString()))
                            },
                            onLongClick = {
                                providerToDelete = provider
                            }
                        )
                    }
                }
            }
        }

        providerToDelete?.let { target ->
            AlertDialog(
                onDismissRequest = { providerToDelete = null },
                title = { Text(stringResource(R.string.setting_provider_delete_title)) },
                text = {
                    Text(stringResource(R.string.setting_provider_delete_body, target.name))
                },
                confirmButton = {
                    TextButton(
                        onClick = {
                            vm.updateSettings(
                                settings.copy(
                                    providers = settings.providers.filter { it.id != target.id },
                                    // If the user removed a built-in default, remember the
                                    // intent so the re-seed pass on settings load doesn't
                                    // resurrect it. Without this gate the row just bobs to
                                    // the bottom of the list on next reload.
                                    deletedBuiltInProviderIds =
                                        if (target.builtIn) settings.deletedBuiltInProviderIds + target.id
                                        else settings.deletedBuiltInProviderIds,
                                    deletedProviderIds = settings.deletedProviderIds + target.id,
                                )
                            )
                            providerToDelete = null
                        }
                    ) {
                        Text(
                            text = stringResource(R.string.setting_provider_delete_confirm),
                            color = MaterialTheme.colorScheme.error,
                        )
                    }
                },
                dismissButton = {
                    TextButton(onClick = { providerToDelete = null }) {
                        Text(stringResource(R.string.setting_provider_delete_cancel))
                    }
                },
            )
        }

        // rhKeyMerge: 合并询问,确认则将新密钥并入已有供应商
        pendingProviderMerge?.let { rhPrompt ->
            val rhNewProvider = rhPrompt.first
            val rhExistingProvider = rhPrompt.second
            AlertDialog(
                onDismissRequest = {
                    vm.updateSettings(settings.copy(providers = listOf(rhNewProvider) + settings.providers))
                    pendingProviderMerge = null
                },
                title = { Text(stringResource(R.string.setting_provider_merge_title)) },
                text = { Text(stringResource(R.string.setting_provider_merge_message, rhExistingProvider.name)) },
                confirmButton = {
                    TextButton(
                        onClick = {
                            vm.updateSettings(
                                settings.copy(
                                    providers = settings.providers.map { rhProvider ->
                                        if (rhProvider.id == rhExistingProvider.id) rhMergeProviderKeys(rhProvider, rhNewProvider)
                                        else rhProvider
                                    }
                                )
                            )
                            pendingProviderMerge = null
                        }
                    ) {
                        Text(stringResource(R.string.setting_provider_merge_confirm))
                    }
                },
                dismissButton = {
                    TextButton(
                        onClick = {
                            vm.updateSettings(settings.copy(providers = listOf(rhNewProvider) + settings.providers))
                            pendingProviderMerge = null
                        }
                    ) {
                        Text(stringResource(R.string.setting_provider_merge_keep))
                    }
                },
            )
        }
    }
}







@Composable
private fun AddButton(onAdd: (ProviderSetting) -> Unit) {
    val dialogState = useEditState<ProviderSetting> {
        onAdd(it.copyProvider(name = it.name.trim()))
    }

    IconButton(
        onClick = {
            dialogState.open(ProviderSetting.OpenAI())
        }
    ) {
        Icon(HugeIcons.Add01, stringResource(R.string.accessibility_add_provider))
    }

    if (dialogState.isEditing) {
        AlertDialog(
            onDismissRequest = {
                dialogState.dismiss()
            },
            title = {
                Text(stringResource(R.string.setting_provider_page_add_provider))
            },
            text = {
                dialogState.currentState?.let {
                    ProviderConfigure(it) { newState ->
                        dialogState.currentState = newState
                    }
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        dialogState.confirm()
                    }
                ) {
                    Text(stringResource(R.string.setting_provider_page_add))
                }
            },
            dismissButton = {
                TextButton(
                    onClick = {
                        dialogState.dismiss()
                    }
                ) {
                    Text(stringResource(R.string.cancel))
                }
            },
        )
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun ProviderItem(
    provider: ProviderSetting,
    modifier: Modifier = Modifier,
    dragHandle: @Composable () -> Unit,
    onClick: () -> Unit,
    onLongClick: () -> Unit = {},
) {
    Card(
        modifier = modifier.combinedClickable(
            onClick = onClick,
            onLongClick = onLongClick,
        ),
        colors = CardDefaults.cardColors(
            containerColor = if (provider.enabled) {
                CustomColors.listItemColors.containerColor
            } else MaterialTheme.colorScheme.errorContainer,
        ),
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            AutoAIIcon(
                name = provider.name,
                modifier = Modifier.size(40.dp)
            )
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text(
                    text = provider.name,
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                ProvideTextStyle(MaterialTheme.typography.labelSmall) {
                    CompositionLocalProvider(LocalContentColor provides LocalContentColor.current.copy(alpha = 0.7f)) {
                        provider.shortDescription()
                    }
                }
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(4.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Tag(type = if (provider.enabled) TagType.SUCCESS else TagType.WARNING) {
                        Text(stringResource(if (provider.enabled) R.string.setting_provider_page_enabled else R.string.setting_provider_page_disabled))
                    }
                    Tag(type = TagType.INFO) {
                        Text(
                            stringResource(
                                R.string.setting_provider_page_model_count,
                                provider.models.size
                            )
                        )
                    }
                    ProviderRequirement.from(provider).forEach { req ->
                        Tag(type = req.severity) {
                            Text(req.label)
                        }
                    }
                }
            }
            dragHandle()
        }
    }
}


// rhKeyMerge: 重复供应商检测与密钥合并工具
private fun ProviderSetting.rhMergeKeyList(): List<String> = when (this) {
    is ProviderSetting.OpenAI -> apiKey
    is ProviderSetting.Google -> apiKey
    is ProviderSetting.Claude -> apiKey
    else -> ""
}.split(Regex("[\\s,]+")).map { it.trim() }.filter { it.isNotEmpty() }

private fun ProviderSetting.rhMergeBaseUrl(): String? = when (this) {
    is ProviderSetting.OpenAI -> baseUrl
    is ProviderSetting.Google -> baseUrl
    is ProviderSetting.Claude -> baseUrl
    else -> null
}?.trim()?.trimEnd('/')?.lowercase()?.takeIf { it.isNotEmpty() }

private fun rhFindDuplicateProvider(
    candidate: ProviderSetting,
    existing: List<ProviderSetting>,
): ProviderSetting? {
    val candidateKeys = candidate.rhMergeKeyList()
    if (candidateKeys.isEmpty()) return null
    val candidateKeySet = candidateKeys.toSet()
    val candidateUrl = candidate.rhMergeBaseUrl()
    return existing.firstOrNull { other ->
        other.javaClass == candidate.javaClass && (
            other.rhMergeKeyList().any { it in candidateKeySet } ||
                (candidateUrl != null && other.rhMergeBaseUrl() == candidateUrl)
        )
    }
}

private fun rhMergeProviderKeys(target: ProviderSetting, source: ProviderSetting): ProviderSetting {
    val targetKeys = target.rhMergeKeyList()
    val added = source.rhMergeKeyList().filter { it !in targetKeys }
    if (added.isEmpty()) return target
    val mergedKeyText = (targetKeys + added).joinToString("\n")
    return when (target) {
        is ProviderSetting.OpenAI -> target.copy(apiKey = mergedKeyText)
        is ProviderSetting.Google -> target.copy(apiKey = mergedKeyText)
        is ProviderSetting.Claude -> target.copy(apiKey = mergedKeyText)
        else -> target
    }
}
