package me.rerere.rikkahub.ui.pages.extensions.workspace

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import me.rerere.rikkahub.data.repository.WorkspaceRepository
import me.rerere.workspace.RootfsInstallProgress
import me.rerere.workspace.RootfsInstallStage

class WorkspaceInstallVM(
    private val workspaceId: String,
    private val repository: WorkspaceRepository,
) : ViewModel() {
    private val _installProgress = MutableStateFlow<RootfsInstallProgress?>(null)
    val installProgress = _installProgress.asStateFlow()

    private val _installError = MutableStateFlow<String?>(null)
    val installError = _installError.asStateFlow()

    fun install(url: String) {
        viewModelScope.launch {
            _installError.value = null
            _installProgress.value = RootfsInstallProgress(stage = RootfsInstallStage.DOWNLOADING)
            try {
                repository.installRootfs(workspaceId, url) { progress ->
                    _installProgress.value = progress
                }
            } catch (e: Exception) {
                _installError.value = e.message ?: "安装失败"
            } finally {
                _installProgress.value = null
            }
        }
    }

    fun dismissError() {
        _installError.value = null
    }
}
