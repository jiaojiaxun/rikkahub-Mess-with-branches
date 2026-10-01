package me.rerere.rikkahub.ui.pages.imggen

import android.app.Application
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.paging.Pager
import androidx.paging.PagingConfig
import androidx.paging.PagingData
import androidx.paging.cachedIn
import androidx.paging.map
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.serialization.Serializable
import me.rerere.ai.provider.ProviderManager
import me.rerere.ai.ui.ImageAspectRatio
import me.rerere.rikkahub.data.ai.ImageGenerationService
import me.rerere.rikkahub.data.datastore.SettingsStore
import me.rerere.rikkahub.data.db.entity.GenMediaEntity
import me.rerere.rikkahub.data.files.FilesManager
import me.rerere.rikkahub.data.repository.GenMediaRepository
import org.koin.java.KoinJavaComponent
import java.io.File
import kotlin.coroutines.cancellation.CancellationException

@Serializable
data class GeneratedImage(
    val id: Int,
    val prompt: String,
    val filePath: String,
    val timestamp: Long,
    val model: String
)

private fun GenMediaEntity.toGeneratedImage(filesManager: FilesManager): GeneratedImage {
    val imagesDir = filesManager.getImagesDir()
    val fullPath = File(imagesDir, this.path.removePrefix("images/")).absolutePath

    return GeneratedImage(
        id = this.id,
        prompt = this.prompt,
        filePath = fullPath,
        timestamp = this.createAt,
        model = this.modelId
    )
}

/**
 * Pure selection logic backing the gallery orphan purge (#39): given every persisted
 * gen-media row and the images directory, returns the entities whose backing file no
 * longer exists on disk. Resolves each entity's file exactly like [toGeneratedImage] does.
 * Extracted as a top-level function so it's unit-testable without constructing the VM.
 */
internal fun selectOrphanedGenMedia(
    entities: List<GenMediaEntity>,
    imagesDir: File,
): List<GenMediaEntity> =
    entities.filter { entity -> !File(imagesDir, entity.path.removePrefix("images/")).exists() }

/**
 * Image page state. Requests run in [ImageGenerationService] (app scope), so leaving the
 * page does not cancel them; this VM only keeps the form inputs and mirrors the job state.
 */
class ImgGenVM(
    context: Application,
    val settingsStore: SettingsStore,
    val providerManager: ProviderManager,
    val genMediaRepository: GenMediaRepository,
    private val filesManager: FilesManager,
) : AndroidViewModel(context) {
    private val service: ImageGenerationService =
        KoinJavaComponent.get(ImageGenerationService::class.java)

    private val _prompt = MutableStateFlow("")
    val prompt: StateFlow<String> = _prompt

    private val _numberOfImages = MutableStateFlow(1)
    val numberOfImages: StateFlow<Int> = _numberOfImages

    private val _aspectRatio = MutableStateFlow(ImageAspectRatio.SQUARE)
    val aspectRatio: StateFlow<ImageAspectRatio> = _aspectRatio

    val isGenerating: StateFlow<Boolean> = service.state.map { it.isGenerating }
        .stateIn(viewModelScope, SharingStarted.Eagerly, service.state.value.isGenerating)

    val error: StateFlow<String?> = service.state.map { it.error }
        .stateIn(viewModelScope, SharingStarted.Eagerly, service.state.value.error)

    val currentGeneratedImages: StateFlow<List<GeneratedImage>> = service.state.map { it.images }
        .stateIn(viewModelScope, SharingStarted.Eagerly, service.state.value.images)

    private val _referenceImages = MutableStateFlow<List<String>>(emptyList())
    val referenceImages: StateFlow<List<String>> = _referenceImages

    val pager = Pager(
        config = PagingConfig(pageSize = 20, enablePlaceholders = false),
        pagingSourceFactory = { genMediaRepository.getAllMedia() }
    )
    val generatedImages: Flow<PagingData<GeneratedImage>> = pager.flow
        .map { pagingData ->
            pagingData.map { entity -> entity.toGeneratedImage(filesManager) }
        }
        .cachedIn(viewModelScope)

    init {
        purgeOrphanedGenMedia()
        // Coming back to the page while a job runs: show its prompt again.
        if (service.state.value.isGenerating) _prompt.value = service.state.value.prompt
    }

    // One-shot purge of gallery entries whose backing file is missing (#39). Room
    // invalidation refreshes the paging flow automatically, so this needs no extra wiring.
    private fun purgeOrphanedGenMedia() {
        viewModelScope.launch(Dispatchers.IO) {
            try {
                val entities = genMediaRepository.getAllMediaList()
                val orphans = selectOrphanedGenMedia(entities, filesManager.getImagesDir())
                orphans.forEach { genMediaRepository.deleteMedia(it.id) }
                if (orphans.isNotEmpty()) {
                    Log.i(TAG, "Purged ${orphans.size} orphaned gallery entries")
                }
            } catch (e: Exception) {
                if (e is CancellationException) return@launch
                Log.e(TAG, "Failed to purge orphaned gallery entries", e)
            }
        }
    }

    fun updatePrompt(prompt: String) {
        _prompt.value = prompt
    }

    fun updateNumberOfImages(count: Int) {
        _numberOfImages.value = count.coerceIn(1, 4)
    }

    fun updateAspectRatio(aspectRatio: ImageAspectRatio) {
        _aspectRatio.value = aspectRatio
    }

    fun addReferenceImages(paths: List<String>) {
        _referenceImages.value = (_referenceImages.value + paths).distinct().take(MAX_REFERENCE_IMAGES)
    }

    fun removeReferenceImage(path: String) {
        _referenceImages.value = _referenceImages.value.filterNot { it == path }
        deleteReferenceFiles(listOf(path))
    }

    fun clearReferenceImages() {
        deleteReferenceFiles(_referenceImages.value)
        _referenceImages.value = emptyList()
    }

    fun clearError() {
        service.clearError()
    }

    fun startNewSession() {
        service.reset()
        clearReferenceImages()
        _prompt.value = ""
    }

    fun generateImage() {
        if (prompt.value.isBlank()) return
        service.start(_prompt.value, _numberOfImages.value, _aspectRatio.value)
    }

    fun editImage() {
        if (prompt.value.isBlank() || referenceImages.value.isEmpty()) return
        service.start(_prompt.value, _numberOfImages.value, _aspectRatio.value, _referenceImages.value)
    }

    fun cancelGeneration() {
        service.cancel()
    }

    fun deleteImage(image: GeneratedImage) {
        viewModelScope.launch {
            try {
                genMediaRepository.deleteMedia(image.id)
                val file = File(image.filePath)
                if (file.exists()) {
                    file.delete()
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to delete image", e)
            }
        }
    }

    private fun deleteReferenceFiles(paths: List<String>) {
        viewModelScope.launch {
            paths.forEach { path ->
                val file = File(path)
                if (file.exists()) {
                    file.delete()
                }
            }
        }
    }

    companion object {
        private const val TAG = "ImgGenVM"
        private const val MAX_REFERENCE_IMAGES = 16
    }
}
