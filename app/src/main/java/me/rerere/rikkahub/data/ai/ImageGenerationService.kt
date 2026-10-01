package me.rerere.rikkahub.data.ai

import android.content.Context
import android.util.Log
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import me.rerere.ai.provider.ImageEditParams
import me.rerere.ai.provider.ImageGenerationParams
import me.rerere.ai.provider.ProviderManager
import me.rerere.ai.ui.ImageAspectRatio
import me.rerere.common.android.appTempFolder
import me.rerere.rikkahub.AppScope
import me.rerere.rikkahub.data.datastore.SettingsStore
import me.rerere.rikkahub.data.datastore.findModelById
import me.rerere.rikkahub.data.datastore.findProvider
import me.rerere.rikkahub.data.db.entity.GenMediaEntity
import me.rerere.rikkahub.data.files.FilesManager
import me.rerere.rikkahub.data.repository.GenMediaRepository
import me.rerere.rikkahub.service.ChatGenerationForegroundService
import me.rerere.rikkahub.ui.pages.imggen.GeneratedImage
import java.io.File
import java.util.concurrent.atomic.AtomicLong

/**
 * Image generation that is not tied to a screen.
 *
 * The image page used to run requests on its ViewModel scope, so leaving the page (or the
 * system killing the activity) cancelled a paid request. Jobs started with [start] run on
 * [AppScope] and keep the generation foreground service alive; results go to the gallery
 * whether or not the page is still open. [generateForTool] is the same pipeline for the
 * generate_image tool, run inside the calling chat generation.
 */
class ImageGenerationService(
    private val context: Context,
    private val appScope: AppScope,
    private val settingsStore: SettingsStore,
    private val providerManager: ProviderManager,
    private val genMediaRepository: GenMediaRepository,
    private val filesManager: FilesManager,
) {
    data class State(
        val isGenerating: Boolean = false,
        val error: String? = null,
        val images: List<GeneratedImage> = emptyList(),
        val prompt: String = "",
    )

    private val _state = MutableStateFlow(State())
    val state: StateFlow<State> = _state.asStateFlow()

    private var job: Job? = null

    // Identifies the newest page job; a cancelled older job must not touch the newer state.
    private val sequence = AtomicLong(0)

    fun start(
        prompt: String,
        count: Int,
        aspectRatio: ImageAspectRatio,
        references: List<String> = emptyList(),
    ) {
        if (prompt.isBlank()) return
        job?.cancel()
        val id = sequence.incrementAndGet()
        _state.value = State(isGenerating = true, prompt = prompt)
        val refs = references.toList()
        job = appScope.launch(Dispatchers.IO) {
            val release = ChatGenerationForegroundService.acquireExternal(context)
            try {
                runGeneration(prompt, count, aspectRatio, refs) { images ->
                    if (sequence.get() == id) _state.update { it.copy(images = images) }
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Log.e(TAG, "Image generation failed", e)
                if (sequence.get() == id) {
                    _state.update { it.copy(error = e.message ?: "Unknown error occurred") }
                }
            } finally {
                release()
                if (sequence.get() == id) _state.update { it.copy(isGenerating = false) }
            }
        }
    }

    fun cancel() {
        job?.cancel()
    }

    fun clearError() {
        _state.update { it.copy(error = null) }
    }

    /** Cancels the page job and clears its results (new session on the image page). */
    fun reset() {
        sequence.incrementAndGet()
        job?.cancel()
        _state.value = State()
    }

    /** Runs one generation for a tool call and returns the saved images. */
    suspend fun generateForTool(
        prompt: String,
        count: Int,
        aspectRatio: ImageAspectRatio,
    ): List<GeneratedImage> {
        val release = ChatGenerationForegroundService.acquireExternal(context)
        try {
            return runGeneration(prompt, count, aspectRatio, emptyList()) { }
        } finally {
            release()
        }
    }

    /**
     * Generates (or edits, when [references] is not empty), saves every final image to the
     * gallery and returns them. [onUpdate] receives the list to display, including the
     * current partial preview.
     */
    private suspend fun runGeneration(
        prompt: String,
        count: Int,
        aspectRatio: ImageAspectRatio,
        references: List<String>,
        onUpdate: (List<GeneratedImage>) -> Unit,
    ): List<GeneratedImage> {
        val settings = settingsStore.settingsFlow.first()
        val model = settings.findModelById(settings.imageGenerationModelId)
            ?: throw IllegalStateException("No image model selected. Pick one on the image creation page.")
        val provider = model.findProvider(settings.providers)
            ?: throw IllegalStateException("Provider not found")
        val handler = providerManager.getProviderByType(provider)
        val n = count.coerceIn(1, 4)
        val isEdit = references.isNotEmpty()
        val images = if (isEdit) {
            handler.editImage(
                provider,
                ImageEditParams(
                    model = model,
                    prompt = prompt,
                    images = references,
                    numOfImages = n,
                    aspectRatio = aspectRatio,
                    customHeaders = model.customHeaders,
                    customBody = model.customBodies,
                ),
            )
        } else {
            handler.generateImage(
                provider,
                ImageGenerationParams(
                    model = model,
                    prompt = prompt,
                    numOfImages = n,
                    aspectRatio = aspectRatio,
                    customHeaders = model.customHeaders,
                    customBody = model.customBodies,
                ),
            )
        }
        val type = if (isEdit) GenMediaEntity.TYPE_IMAGE_EDIT else GenMediaEntity.TYPE_IMAGE_GENERATION
        val sourcePaths = if (isEdit) references.joinToString("\n") else null
        val modelName = model.displayName

        val finals = mutableListOf<GeneratedImage>()
        var previewFile: File? = null
        try {
            images.collect { item ->
                previewFile?.delete()
                previewFile = null
                val now = System.currentTimeMillis()
                if (item.partial) {
                    val index = item.partialImageIndex ?: finals.size
                    val file = filesManager.createImageFileFromBase64(
                        item.data,
                        File(context.appTempFolder, "imggen_${now}_${index}.png").absolutePath,
                    )
                    previewFile = file
                    onUpdate(finals + GeneratedImage(0, prompt, file.absolutePath, now, modelName))
                } else {
                    val file = filesManager.createImageFileFromBase64(
                        item.data,
                        File(filesManager.getImagesDir(), "${now}_${safeName(modelName)}_${finals.size}.png").absolutePath,
                    )
                    genMediaRepository.insertMedia(
                        GenMediaEntity(
                            path = "images/${file.name}",
                            modelId = modelName,
                            prompt = prompt,
                            createAt = now,
                            type = type,
                            sourcePaths = sourcePaths,
                        )
                    )
                    finals += GeneratedImage(0, prompt, file.absolutePath, now, modelName)
                    onUpdate(finals.toList())
                }
            }
        } finally {
            previewFile?.delete()
        }
        return finals.toList()
    }

    private fun safeName(name: String): String = name.replace(Regex("[^A-Za-z0-9._-]"), "_").take(40)

    companion object {
        private const val TAG = "ImageGenerationService"
    }
}
