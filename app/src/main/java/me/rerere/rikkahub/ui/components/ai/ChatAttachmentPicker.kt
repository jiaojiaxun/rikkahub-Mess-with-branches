package me.rerere.rikkahub.ui.components.ai

import android.content.Context
import android.net.Uri
import android.util.Log
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalResources
import androidx.core.content.FileProvider
import androidx.core.net.toUri
import com.dokar.sonner.ToastType
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import me.rerere.ai.ui.UIMessagePart
import me.rerere.common.android.appTempFolder
import me.rerere.rikkahub.R
import me.rerere.rikkahub.data.datastore.Settings
import me.rerere.rikkahub.data.datastore.getCurrentAssistant
import me.rerere.rikkahub.data.files.FilesManager
import me.rerere.rikkahub.data.repository.WorkspaceRepository
import me.rerere.rikkahub.ui.components.ui.permission.PermissionCamera
import me.rerere.rikkahub.ui.components.ui.permission.PermissionManager
import me.rerere.rikkahub.ui.components.ui.permission.rememberPermissionState
import me.rerere.rikkahub.ui.context.LocalToaster
import me.rerere.rikkahub.ui.hooks.ChatInputState
import me.rerere.rikkahub.utils.ImageUtils
import me.rerere.rikkahub.utils.isAllowedFileType
import me.rerere.rikkahub.utils.looksLikeText
import me.rerere.workspace.WorkspaceStorageArea
import org.koin.compose.koinInject
import java.io.File
import kotlin.uuid.Uuid

private const val TAG = "ChatAttachmentPicker"

/** Workspace folder that receives files the model cannot take as attachments. */
private const val WORKSPACE_UPLOAD_DIR = "uploads"

internal data class ChatAttachmentPickerActions(
    val onTakePicture: () -> Unit,
    val onPickImage: () -> Unit,
    val onPickVideo: () -> Unit,
    val onPickAudio: () -> Unit,
    val onPickFile: () -> Unit,
)

@Composable
internal fun rememberChatAttachmentPickerActions(
    inputState: ChatInputState,
    setting: Settings,
    onAttachmentAdded: () -> Unit,
): ChatAttachmentPickerActions {
    val context = LocalContext.current
    val resources = LocalResources.current
    val toaster = LocalToaster.current
    val scope = rememberCoroutineScope()
    val filesManager: FilesManager = koinInject()
    val workspaceRepository: WorkspaceRepository = koinInject()
    val cameraPermission = rememberPermissionState(PermissionCamera)
    PermissionManager(permissionState = cameraPermission)

    var cameraOutputUri by remember { mutableStateOf<Uri?>(null) }
    var cameraOutputFile by remember { mutableStateOf<File?>(null) }
    val (_, launchCameraCrop) = useCropLauncher(
        onCroppedImageReady = { croppedUri ->
            inputState.addImages(filesManager.createChatFilesByContents(listOf(croppedUri)))
            onAttachmentAdded()
        },
        onCleanup = {
            cameraOutputFile?.delete()
            cameraOutputFile = null
            cameraOutputUri = null
        }
    )
    val cameraLauncher = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { captureSuccessful ->
        if (captureSuccessful && cameraOutputUri != null) {
            if (setting.displaySetting.skipCropImage) {
                inputState.addImages(filesManager.createChatFilesByContents(listOf(cameraOutputUri!!)))
                cameraOutputFile?.delete()
                cameraOutputFile = null
                cameraOutputUri = null
                onAttachmentAdded()
            } else {
                launchCameraCrop(cameraOutputUri!!)
            }
        } else {
            cameraOutputFile?.delete()
            cameraOutputFile = null
            cameraOutputUri = null
        }
    }
    val onTakePicture: () -> Unit = {
        if (cameraPermission.allRequiredPermissionsGranted) {
            cameraOutputFile = context.cacheDir.resolve("camera_${Uuid.random()}.jpg")
            cameraOutputUri = FileProvider.getUriForFile(
                context, "${context.packageName}.fileprovider", cameraOutputFile!!
            )
            cameraLauncher.launch(cameraOutputUri!!)
        } else {
            cameraPermission.requestPermissions()
        }
    }

    var preCropTempFile by remember { mutableStateOf<File?>(null) }
    val (_, launchImageCrop) = useCropLauncher(
        onCroppedImageReady = { croppedUri ->
            inputState.addImages(filesManager.createChatFilesByContents(listOf(croppedUri)))
            onAttachmentAdded()
        },
        onCleanup = {
            preCropTempFile?.delete()
            preCropTempFile = null
        }
    )
    val imagePickerLauncher =
        rememberLauncherForActivityResult(ActivityResultContracts.GetMultipleContents()) { selectedUris ->
            if (selectedUris.isNotEmpty()) {
                Log.d("ImagePickButton", "Selected URIs: $selectedUris")
                if (setting.displaySetting.skipCropImage) {
                    inputState.addImages(filesManager.createChatFilesByContents(selectedUris))
                    onAttachmentAdded()
                } else if (selectedUris.size == 1) {
                    val tempFile = File(context.appTempFolder, "pick_temp_${System.currentTimeMillis()}.jpg")
                    runCatching {
                        val source = selectedUris.first()
                        // HEIF/HEIC（尤其 HDR HEIF）交给 UCrop 前先解码转为 JPEG，规避裁剪解码失败
                        val converted = ImageUtils.isHeifImage(context, source) &&
                            ImageUtils.convertHeifToJpeg(context, source, tempFile)
                        if (!converted) {
                            context.contentResolver.openInputStream(source)?.use { input ->
                                tempFile.outputStream().use { output -> input.copyTo(output) }
                            }
                        }
                        preCropTempFile = tempFile
                        launchImageCrop(tempFile.toUri())
                    }.onFailure {
                        Log.e("ImagePickButton", "Failed to copy image to temp, falling back", it)
                        launchImageCrop(selectedUris.first())
                    }
                } else {
                    inputState.addImages(filesManager.createChatFilesByContents(selectedUris))
                    onAttachmentAdded()
                }
            } else {
                Log.d("ImagePickButton", "No images selected")
            }
        }

    val videoPickerLauncher =
        rememberLauncherForActivityResult(ActivityResultContracts.GetMultipleContents()) { selectedUris ->
            if (selectedUris.isNotEmpty()) {
                inputState.addVideos(filesManager.createChatFilesByContents(selectedUris))
                onAttachmentAdded()
            }
        }

    val audioPickerLauncher =
        rememberLauncherForActivityResult(ActivityResultContracts.GetMultipleContents()) { selectedUris ->
            if (selectedUris.isNotEmpty()) {
                inputState.addAudios(filesManager.createChatFilesByContents(selectedUris))
                onAttachmentAdded()
            }
        }

    // Any file can be picked. Documents the model can read (known text/office/PDF types, or
    // anything whose content is UTF-8 text) become attachments; everything else is copied
    // into the assistant's workspace and its path is added to the message so the model can
    // use workspace tools on it.
    val filePickerLauncher =
        rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
            if (uris.isEmpty()) return@rememberLauncherForActivityResult
            scope.launch {
                val documents = mutableListOf<UIMessagePart.Document>()
                val importedPaths = mutableListOf<String>()
                val workspaceId = setting.getCurrentAssistant().workspaceId?.toString()
                uris.forEach { uri ->
                    val fileName = filesManager.getFileNameFromUri(uri) ?: "file"
                    val rawMime = filesManager.getFileMimeType(uri)
                    val attachMime = when {
                        isAllowedFileType(fileName, rawMime ?: "application/octet-stream") ->
                            rawMime ?: "text/plain"
                        withContext(Dispatchers.IO) { context.isTextContent(uri) } -> "text/plain"
                        else -> null
                    }
                    if (attachMime != null) {
                        val localUri = withContext(Dispatchers.IO) {
                            filesManager.createChatFilesByContents(listOf(uri)).firstOrNull()
                        }
                        if (localUri == null) {
                            toaster.show(
                                resources.getString(R.string.chat_input_file_read_failed, fileName),
                                type = ToastType.Error
                            )
                        } else {
                            documents += UIMessagePart.Document(
                                url = localUri.toString(),
                                fileName = fileName,
                                mime = attachMime,
                            )
                        }
                        return@forEach
                    }
                    if (workspaceId == null) {
                        toaster.show(
                            resources.getString(R.string.chat_input_file_no_workspace, fileName),
                            type = ToastType.Error
                        )
                        return@forEach
                    }
                    val path = importToWorkspace(context, workspaceRepository, workspaceId, uri, fileName)
                    if (path == null) {
                        toaster.show(
                            resources.getString(R.string.chat_input_file_read_failed, fileName),
                            type = ToastType.Error
                        )
                    } else {
                        importedPaths += path
                        toaster.show(
                            resources.getString(R.string.chat_input_file_imported_to_workspace, fileName, path),
                            type = ToastType.Success
                        )
                    }
                }
                if (documents.isNotEmpty()) inputState.addFiles(documents)
                if (importedPaths.isNotEmpty()) {
                    val prefix = if (inputState.textContent.text.isEmpty()) "" else "\n"
                    inputState.appendText(
                        prefix + importedPaths.joinToString("\n") { "[File imported to workspace: $it]" }
                    )
                }
                if (documents.isNotEmpty() || importedPaths.isNotEmpty()) onAttachmentAdded()
            }
        }

    return ChatAttachmentPickerActions(
        onTakePicture = onTakePicture,
        onPickImage = { imagePickerLauncher.launch("image/*") },
        onPickVideo = { videoPickerLauncher.launch("video/*") },
        onPickAudio = { audioPickerLauncher.launch("audio/*") },
        onPickFile = { filePickerLauncher.launch(arrayOf("*/*")) },
    )
}

/** Reads the first 8 KB of [uri] and checks whether it is UTF-8 text. */
private fun Context.isTextContent(uri: Uri): Boolean = runCatching {
    contentResolver.openInputStream(uri)?.use { input ->
        val buffer = ByteArray(8 * 1024)
        var total = 0
        while (total < buffer.size) {
            val read = input.read(buffer, total, buffer.size - total)
            if (read <= 0) break
            total += read
        }
        looksLikeText(buffer.copyOf(total))
    } ?: false
}.getOrDefault(false)

/**
 * Copies [uri] into `uploads/` of the workspace and returns the workspace-relative path, or
 * null on failure. When the name is taken a timestamp prefix is added instead of overwriting.
 */
private suspend fun importToWorkspace(
    context: Context,
    repository: WorkspaceRepository,
    workspaceId: String,
    uri: Uri,
    fileName: String,
): String? = withContext(Dispatchers.IO) {
    val safeName = fileName.substringAfterLast('/').substringAfterLast('\\')
        .takeIf { it.isNotBlank() && it != "." && it != ".." } ?: "file"
    suspend fun importAs(name: String): String {
        val input = context.contentResolver.openInputStream(uri) ?: error("cannot open $fileName")
        return input.use {
            repository.importFile(workspaceId, WorkspaceStorageArea.FILES, WORKSPACE_UPLOAD_DIR, name, it).path
        }
    }
    runCatching { importAs(safeName) }
        .recoverCatching { importAs("${System.currentTimeMillis()}_$safeName") }
        .onFailure { Log.e(TAG, "import to workspace failed: $fileName", it) }
        .getOrNull()
}
