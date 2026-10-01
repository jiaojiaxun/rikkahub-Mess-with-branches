package me.rerere.rikkahub.ui.pages.setting

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import me.rerere.rikkahub.AppScope
import me.rerere.rikkahub.data.datastore.Settings
import me.rerere.rikkahub.data.datastore.SettingsStore
import me.rerere.rikkahub.data.ai.mcp.McpManager

class SettingVM(
    private val settingsStore: SettingsStore,
    private val mcpManager: McpManager,
    private val appScope: AppScope,
) :
    ViewModel() {
    val settings: StateFlow<Settings> = settingsStore.settingsFlow
        .stateIn(viewModelScope, SharingStarted.Lazily, Settings(init = true, providers = emptyList()))

    fun updateSettings(settings: Settings) {
        // Settings edits must survive leaving the settings screen immediately. Using the
        // application scope prevents a ViewModel cancellation from dropping the DataStore edit
        // while the user exits or navigates away after typing.
        appScope.launch {
            settingsStore.update(settings)
        }
    }

    fun updateSettings(transform: (Settings) -> Settings) {
        appScope.launch {
            settingsStore.update(transform)
        }
    }

    /**
     * Catalogs fetched with Provider.listModels(), keyed by a stable provider key
     * (id + baseUrl + apiKey). Model add/remove/reorder must not re-request the list, so
     * the fetch site looks here before hitting the network. Null means "not fetched".
     */
    private val fetchedModelCatalogs = MutableStateFlow<Map<String, List<me.rerere.ai.provider.Model>>>(emptyMap())

    fun cachedModelCatalog(key: String): List<me.rerere.ai.provider.Model>? =
        fetchedModelCatalogs.value[key]

    fun putModelCatalog(key: String, models: List<me.rerere.ai.provider.Model>) {
        fetchedModelCatalogs.value = fetchedModelCatalogs.value + (key to models)
    }

    fun clearModelCatalog(key: String) {
        fetchedModelCatalogs.value = fetchedModelCatalogs.value - key
    }
}
