#!/usr/bin/env python3
# rhRemote352a: SSH 工作区编辑页 + ViewModel（纯新增，不碰导航与列表）
# 适配 fork 的组件: 用 Card + Column + OutlinedTextField, 不依赖上游的 CardGroupIcon/switchItem/formItem。
import os

MARK = "rhRemote352a"
DIAG = "ci_diag_batch352a_remote.txt"
ROOT = os.environ.get("GITHUB_WORKSPACE", os.getcwd())


def write(path, text):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


VM = r'''package me.rerere.rikkahub.ui.pages.extensions.workspace

import androidx.annotation.StringRes
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import me.rerere.rikkahub.R
import me.rerere.rikkahub.data.model.SshWorkspaceDraft
import me.rerere.rikkahub.data.repository.WorkspaceRepository
import me.rerere.workspace.ssh.SshAuthType
import me.rerere.workspace.ssh.SshHostKey
import me.rerere.workspace.ssh.SshHostKeyChangedException
import me.rerere.workspace.ssh.SshProbeResult
import me.rerere.workspace.ssh.SshUnknownHostKeyException

class WorkspaceSshEditorVM(
    private val id: String?,
    private val repository: WorkspaceRepository,
) : ViewModel() {
    private val _state = MutableStateFlow(WorkspaceSshEditorState(loading = id != null))
    val state = _state.asStateFlow()

    val isNew: Boolean = id == null

    init {
        if (id != null) {
            viewModelScope.launch {
                val workspace = repository.getById(id)
                val settings = workspace?.sshSettings()
                _state.update { state ->
                    if (workspace == null || settings == null) {
                        state.copy(
                            loading = false,
                            error = SshEditorError.Resource(R.string.workspace_ssh_editor_not_found)
                        )
                    } else {
                        state.copy(
                            loading = false,
                            name = workspace.name,
                            host = settings.host,
                            port = settings.port.toString(),
                            username = settings.username,
                            authType = settings.authType,
                            remoteDir = settings.remoteDir,
                            hostKey = settings.hostKey,
                            hasSavedPassword = settings.encryptedPassword != null,
                            hasSavedPrivateKey = settings.encryptedPrivateKey != null,
                        )
                    }
                }
            }
        }
    }

    fun update(transform: (WorkspaceSshEditorState) -> WorkspaceSshEditorState) {
        _state.update { old ->
            // 测试和保存针对的是开始时的表单快照, 期间不接受修改
            if (old.busy) return@update old
            var new = transform(old)
            // 信任的主机密钥属于原来的地址, 地址变了必须重新确认
            if (new.host.trim() != old.host.trim() || new.port != old.port) {
                new = new.copy(hostKey = null, probeResult = null)
            }
            new
        }
    }

    fun testConnection() = runProbe(saveAfter = false)

    /** 保存前先测试连接, 顺便确认主机密钥; 连接失败时询问是否仍然保存 */
    fun save() = runProbe(saveAfter = true)

    /** 保存测试失败的那份配置 */
    fun saveAnyway() {
        val draft = state.value.saveAnywayDraft ?: return
        _state.update { it.copy(error = null, saveAnywayDraft = null) }
        persist(draft)
    }

    fun trustHostKey() {
        val pending = state.value.pendingHostKey ?: return
        // 指纹属于测试时的那份配置, 表单变了就不能套用到新地址上
        if (state.value.toDraftOrNull()?.withoutHostKey() != pending.draft.withoutHostKey()) {
            _state.update { it.copy(pendingHostKey = null) }
            return
        }
        _state.update { it.copy(hostKey = pending.actual, pendingHostKey = null) }
        runProbe(saveAfter = pending.saveAfter)
    }

    fun dismissHostKey() {
        _state.update { it.copy(pendingHostKey = null) }
    }

    fun dismissError() {
        _state.update { it.copy(error = null, saveAnywayDraft = null) }
    }

    private fun runProbe(saveAfter: Boolean) {
        val current = state.value
        if (current.busy) return
        val draft = current.toDraftOrNull() ?: run {
            _state.update { it.copy(error = SshEditorError.Resource(R.string.workspace_ssh_editor_missing_fields)) }
            return
        }
        _state.update { it.copy(testing = true, error = null, saveAnywayDraft = null) }
        viewModelScope.launch {
            try {
                val result = repository.probeSsh(id, draft)
                // 没填工作目录时默认用远程用户的主目录
                val tested = draft.copy(remoteDir = draft.remoteDir.ifBlank { result.homeDir })
                _state.update { it.copy(testing = false, probeResult = result, remoteDir = tested.remoteDir) }
                if (saveAfter) persist(tested)
            } catch (e: CancellationException) {
                throw e
            } catch (e: SshUnknownHostKeyException) {
                _state.update {
                    it.copy(testing = false, pendingHostKey = PendingHostKey(draft, e.hostKey, null, saveAfter))
                }
            } catch (e: SshHostKeyChangedException) {
                _state.update {
                    it.copy(testing = false, pendingHostKey = PendingHostKey(draft, e.actual, e.expected, saveAfter))
                }
            } catch (e: Exception) {
                _state.update {
                    it.copy(
                        testing = false,
                        probeResult = null,
                        error = SshEditorError.Message(e.message ?: e.javaClass.simpleName),
                        saveAnywayDraft = draft.takeIf { saveAfter },
                    )
                }
            }
        }
    }

    private fun persist(draft: SshWorkspaceDraft) {
        if (draft.remoteDir.isBlank()) {
            _state.update { it.copy(error = SshEditorError.Resource(R.string.workspace_ssh_editor_missing_remote_dir)) }
            return
        }
        _state.update { it.copy(saving = true) }
        viewModelScope.launch {
            try {
                repository.saveSsh(id, draft)
                _state.update { it.copy(saving = false, saved = true) }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _state.update {
                    it.copy(
                        saving = false,
                        error = e.message?.let(SshEditorError::Message)
                            ?: SshEditorError.Resource(R.string.workspace_ssh_editor_save_failed)
                    )
                }
            }
        }
    }

    private fun WorkspaceSshEditorState.toDraftOrNull(): SshWorkspaceDraft? {
        val port = port.trim().toIntOrNull()?.takeIf { it in 1..65535 } ?: return null
        if (host.isBlank() || username.isBlank()) return null
        return SshWorkspaceDraft(
            name = name,
            host = host,
            port = port,
            username = username,
            authType = authType,
            password = password,
            privateKey = privateKey,
            passphrase = passphrase,
            remoteDir = remoteDir.trim(),
            hostKey = hostKey,
        )
    }

    private fun SshWorkspaceDraft.withoutHostKey() = copy(hostKey = null)
}

data class WorkspaceSshEditorState(
    val loading: Boolean = false,
    val name: String = "",
    val host: String = "",
    val port: String = "22",
    val username: String = "",
    val authType: SshAuthType = SshAuthType.PASSWORD,
    val password: String = "",
    val privateKey: String = "",
    val passphrase: String = "",
    val remoteDir: String = "",
    val hostKey: SshHostKey? = null,
    val hasSavedPassword: Boolean = false,
    val hasSavedPrivateKey: Boolean = false,
    val testing: Boolean = false,
    val saving: Boolean = false,
    val probeResult: SshProbeResult? = null,
    val pendingHostKey: PendingHostKey? = null,
    val error: SshEditorError? = null,
    val saveAnywayDraft: SshWorkspaceDraft? = null,
    val saved: Boolean = false,
) {
    val busy: Boolean
        get() = loading || testing || saving

    val canSaveAnyway: Boolean
        get() = saveAnywayDraft != null
}

/** 表单自己的提示用字符串资源, 连接和保存失败时直接显示异常信息 */
sealed interface SshEditorError {
    data class Resource(@StringRes val id: Int) : SshEditorError

    data class Message(val text: String) : SshEditorError
}

/** 等待用户确认的主机密钥, 属于 [draft] 这份配置 */
data class PendingHostKey(
    val draft: SshWorkspaceDraft,
    val actual: SshHostKey,
    val expected: SshHostKey?,
    val saveAfter: Boolean,
) {
    val address: String
        get() = "${draft.host}:${draft.port}"
}
'''

PAGE = r'''package me.rerere.rikkahub.ui.pages.extensions.workspace

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
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
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import me.rerere.hugeicons.HugeIcons
import me.rerere.hugeicons.stroke.FileImport
import me.rerere.hugeicons.stroke.View
import me.rerere.hugeicons.stroke.ViewOff
import me.rerere.rikkahub.R
import me.rerere.rikkahub.ui.components.nav.BackButton
import me.rerere.rikkahub.ui.context.LocalNavController
import me.rerere.rikkahub.ui.theme.CustomColors
import me.rerere.workspace.ssh.SshAuthType
import org.koin.androidx.compose.koinViewModel
import org.koin.core.parameter.parametersOf
import java.io.ByteArrayOutputStream
import java.io.InputStream

private const val MAX_PRIVATE_KEY_BYTES = 64 * 1024

@Composable
fun WorkspaceSshEditorPage(id: String?) {
    val navController = LocalNavController.current
    val vm: WorkspaceSshEditorVM = koinViewModel(key = "ssh-editor-$id", parameters = { parametersOf(id) })
    val state by vm.state.collectAsStateWithLifecycle()
    val editable = !state.busy

    LaunchedEffect(state.saved) {
        if (state.saved) navController.popBackStack()
    }

    val privateKeyPicker = rememberPrivateKeyPicker { key -> vm.update { it.copy(privateKey = key) } }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        if (vm.isNew) {
                            stringResource(R.string.workspace_ssh_editor_title_new)
                        } else {
                            stringResource(R.string.workspace_ssh_editor_title_edit)
                        }
                    )
                },
                navigationIcon = { BackButton() },
                actions = {
                    IconButton(onClick = vm::save, enabled = !state.busy) {
                        Text(stringResource(R.string.workspace_ssh_editor_save))
                    }
                },
                colors = CustomColors.topBarColors,
            )
        },
        containerColor = CustomColors.topBarColors.containerColor,
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .imePadding(),
            contentPadding = PaddingValues(
                start = 16.dp,
                end = 16.dp,
                top = innerPadding.calculateTopPadding() + 8.dp,
                bottom = innerPadding.calculateBottomPadding() + 16.dp,
            ),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            item {
                SshFormCard(title = stringResource(R.string.workspace_ssh_editor_basic)) {
                    OutlinedTextField(
                        enabled = editable,
                        value = state.name,
                        onValueChange = { value -> vm.update { it.copy(name = value) } },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text(stringResource(R.string.workspace_ssh_editor_name)) },
                        placeholder = { Text(stringResource(R.string.workspace_ssh_editor_name_placeholder)) },
                        singleLine = true,
                    )
                }
            }

            item {
                SshFormCard(title = stringResource(R.string.workspace_ssh_editor_connection)) {
                    OutlinedTextField(
                        enabled = editable,
                        value = state.host,
                        onValueChange = { value -> vm.update { it.copy(host = value.trim()) } },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text(stringResource(R.string.workspace_ssh_editor_host)) },
                        placeholder = { Text(stringResource(R.string.workspace_ssh_editor_host_placeholder)) },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                    )
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        enabled = editable,
                        value = state.port,
                        onValueChange = { value ->
                            vm.update { it.copy(port = value.filter(Char::isDigit).take(5)) }
                        },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text(stringResource(R.string.workspace_ssh_editor_port)) },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    )
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        enabled = editable,
                        value = state.username,
                        onValueChange = { value -> vm.update { it.copy(username = value.trim()) } },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text(stringResource(R.string.workspace_ssh_editor_username)) },
                        singleLine = true,
                    )
                }
            }

            item {
                SshFormCard(title = stringResource(R.string.workspace_ssh_editor_auth)) {
                    SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {
                        val options = listOf(
                            SshAuthType.PASSWORD to stringResource(R.string.workspace_ssh_editor_password),
                            SshAuthType.PRIVATE_KEY to stringResource(R.string.workspace_ssh_editor_private_key),
                        )
                        options.forEachIndexed { index, (type, label) ->
                            SegmentedButton(
                                enabled = editable,
                                selected = state.authType == type,
                                onClick = { vm.update { it.copy(authType = type) } },
                                shape = SegmentedButtonDefaults.itemShape(index, options.size),
                            ) {
                                Text(label)
                            }
                        }
                    }
                    Spacer(Modifier.height(8.dp))
                    when (state.authType) {
                        SshAuthType.PASSWORD -> SecretTextField(
                            enabled = editable,
                            value = state.password,
                            onValueChange = { value -> vm.update { it.copy(password = value) } },
                            label = stringResource(R.string.workspace_ssh_editor_password),
                            placeholder = if (state.hasSavedPassword) {
                                stringResource(R.string.workspace_ssh_editor_saved_keep)
                            } else {
                                null
                            },
                        )

                        SshAuthType.PRIVATE_KEY -> {
                            OutlinedTextField(
                                enabled = editable,
                                value = state.privateKey,
                                onValueChange = { value -> vm.update { it.copy(privateKey = value) } },
                                modifier = Modifier.fillMaxWidth(),
                                label = { Text(stringResource(R.string.workspace_ssh_editor_private_key)) },
                                placeholder = {
                                    Text(
                                        if (state.hasSavedPrivateKey) {
                                            stringResource(R.string.workspace_ssh_editor_saved_keep)
                                        } else {
                                            "-----BEGIN OPENSSH PRIVATE KEY-----"
                                        }
                                    )
                                },
                                textStyle = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace),
                                minLines = 3,
                                maxLines = 8,
                            )
                            Spacer(Modifier.height(8.dp))
                            OutlinedButton(
                                enabled = editable,
                                onClick = { privateKeyPicker.launch(arrayOf("*/*")) },
                                modifier = Modifier.fillMaxWidth(),
                            ) {
                                Icon(
                                    HugeIcons.FileImport,
                                    contentDescription = null,
                                    modifier = Modifier.size(ButtonDefaults.IconSize),
                                )
                                Spacer(Modifier.width(ButtonDefaults.IconSpacing))
                                Text(stringResource(R.string.workspace_ssh_editor_import_key))
                            }
                            Spacer(Modifier.height(8.dp))
                            SecretTextField(
                                enabled = editable,
                                value = state.passphrase,
                                onValueChange = { value -> vm.update { it.copy(passphrase = value) } },
                                label = stringResource(R.string.workspace_ssh_editor_passphrase),
                                placeholder = stringResource(R.string.workspace_ssh_editor_passphrase_placeholder),
                            )
                        }
                    }
                }
            }

            item {
                SshFormCard(title = stringResource(R.string.workspace_ssh_editor_working_dir)) {
                    OutlinedTextField(
                        enabled = editable,
                        value = state.remoteDir,
                        onValueChange = { value -> vm.update { it.copy(remoteDir = value.trim()) } },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text(stringResource(R.string.workspace_ssh_editor_remote_dir)) },
                        placeholder = { Text("/home/user/project") },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                    )
                }
            }

            item {
                SshFormCard(title = stringResource(R.string.workspace_ssh_editor_security)) {
                    Text(
                        text = stringResource(R.string.workspace_ssh_editor_host_key),
                        style = MaterialTheme.typography.titleSmall,
                    )
                    Spacer(Modifier.height(4.dp))
                    if (state.hostKey == null) {
                        Text(
                            text = stringResource(R.string.workspace_ssh_editor_host_key_unconfirmed),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    } else {
                        Text(
                            text = "${state.hostKey?.type}\n${state.hostKey?.fingerprint}",
                            style = MaterialTheme.typography.bodySmall,
                            fontFamily = FontFamily.Monospace,
                        )
                    }
                }
            }

            item {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    FilledTonalButton(
                        onClick = vm::testConnection,
                        enabled = !state.busy,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        if (state.testing) {
                            CircularProgressIndicator(modifier = Modifier.size(ButtonDefaults.IconSize))
                        }
                        Spacer(Modifier.width(ButtonDefaults.IconSpacing))
                        Text(
                            if (state.testing) {
                                stringResource(R.string.workspace_ssh_editor_connecting)
                            } else {
                                stringResource(R.string.workspace_ssh_editor_test)
                            }
                        )
                    }
                    state.probeResult?.let { result ->
                        SshFormCard(title = stringResource(R.string.workspace_ssh_editor_connected)) {
                            Text(
                                text = stringResource(R.string.workspace_ssh_editor_shell) + ": " + result.shell,
                                style = MaterialTheme.typography.bodySmall,
                            )
                            Spacer(Modifier.height(4.dp))
                            Text(
                                text = when {
                                    state.remoteDir.isBlank() || state.remoteDir == result.homeDir ->
                                        stringResource(R.string.workspace_ssh_editor_home_dir, result.homeDir)
                                    result.remoteDirExists -> state.remoteDir
                                    else -> stringResource(R.string.workspace_ssh_editor_dir_missing, state.remoteDir)
                                },
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }
                }
            }
        }
    }

    state.pendingHostKey?.let { pending ->
        HostKeyDialog(
            pending = pending,
            address = pending.address,
            onTrust = vm::trustHostKey,
            onDismiss = vm::dismissHostKey,
        )
    }

    state.error?.let { error ->
        val message = when (error) {
            is SshEditorError.Resource -> stringResource(error.id)
            is SshEditorError.Message -> error.text
        }
        AlertDialog(
            onDismissRequest = vm::dismissError,
            title = {
                Text(
                    if (state.canSaveAnyway) {
                        stringResource(R.string.workspace_ssh_editor_connect_failed)
                    } else {
                        stringResource(R.string.workspace_ssh_editor_error)
                    }
                )
            },
            text = {
                Text(
                    if (state.canSaveAnyway) {
                        stringResource(R.string.workspace_ssh_editor_save_anyway_message, message)
                    } else {
                        message
                    }
                )
            },
            confirmButton = {
                if (state.canSaveAnyway) {
                    TextButton(onClick = vm::saveAnyway) {
                        Text(stringResource(R.string.workspace_ssh_editor_save_anyway))
                    }
                } else {
                    TextButton(onClick = vm::dismissError) { Text(stringResource(R.string.confirm)) }
                }
            },
            dismissButton = if (state.canSaveAnyway) {
                { TextButton(onClick = vm::dismissError) { Text(stringResource(R.string.cancel)) } }
            } else {
                null
            },
        )
    }
}

@Composable
private fun SshFormCard(title: String, content: @Composable () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
        ) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleSmallEmphasized,
                color = MaterialTheme.colorScheme.primary,
            )
            Spacer(Modifier.height(8.dp))
            content()
        }
    }
}

@Composable
private fun rememberPrivateKeyPicker(onPicked: (String) -> Unit): androidx.activity.compose.ManagedActivityResultLauncher<Array<String>, Uri?> {
    val context = LocalContext.current
    return rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        val text = runCatching {
            context.contentResolver.openInputStream(uri)?.use { it.readLimited(MAX_PRIVATE_KEY_BYTES) }
        }.getOrNull()
        if (text != null) onPicked(text.trim())
    }
}

@Composable
private fun SecretTextField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    placeholder: String?,
    enabled: Boolean,
) {
    var visible by remember { mutableStateOf(false) }
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        modifier = Modifier.fillMaxWidth(),
        enabled = enabled,
        label = { Text(label) },
        placeholder = placeholder?.let { { Text(it) } },
        singleLine = true,
        visualTransformation = if (visible) VisualTransformation.None else PasswordVisualTransformation(),
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
        trailingIcon = {
            IconButton(onClick = { visible = !visible }) {
                Icon(if (visible) HugeIcons.ViewOff else HugeIcons.View, contentDescription = null)
            }
        },
    )
}

@Composable
private fun HostKeyDialog(
    pending: PendingHostKey,
    address: String,
    onTrust: () -> Unit,
    onDismiss: () -> Unit,
) {
    val changed = pending.expected != null
    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Text(
                stringResource(
                    if (changed) R.string.workspace_ssh_editor_host_key_changed
                    else R.string.workspace_ssh_editor_host_key_confirm
                )
            )
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    if (changed) {
                        stringResource(R.string.workspace_ssh_editor_host_key_changed_message, address)
                    } else {
                        val keyFile = pending.actual.type.removePrefix("ssh-").substringBefore('-')
                        stringResource(
                            R.string.workspace_ssh_editor_host_key_first_message,
                            address,
                            "ssh-keygen -lf /etc/ssh/ssh_host_${keyFile}_key.pub",
                        )
                    }
                )
                Text(
                    text = "${pending.actual.type}\n${pending.actual.fingerprint}",
                    style = MaterialTheme.typography.bodySmall,
                    fontFamily = FontFamily.Monospace,
                    modifier = Modifier.padding(vertical = 4.dp),
                )
            }
        },
        confirmButton = {
            if (changed) {
                Button(
                    onClick = onTrust,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.error,
                        contentColor = MaterialTheme.colorScheme.onError,
                    ),
                ) { Text(stringResource(R.string.workspace_ssh_editor_trust_new_key)) }
            } else {
                TextButton(onClick = onTrust) { Text(stringResource(R.string.workspace_ssh_editor_trust_continue)) }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text(stringResource(R.string.cancel)) }
        },
    )
}

// 私钥文件很小, 超过上限的多半是选错了文件, 不整个读进内存
private fun InputStream.readLimited(limit: Int): String? {
    val output = ByteArrayOutputStream()
    val buffer = ByteArray(8 * 1024)
    while (true) {
        val read = read(buffer)
        if (read < 0) break
        if (output.size() + read > limit) return null
        output.write(buffer, 0, read)
    }
    return output.toString(Charsets.UTF_8.name())
}
'''


def main():
    diag = []
    files = [
        ("app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/WorkspaceSshEditorVM.kt", VM),
        ("app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/WorkspaceSshEditorPage.kt", PAGE),
    ]
    ok = True
    for path, content in files:
        if os.path.exists(path):
            diag.append(path.rsplit("/", 1)[-1] + ":exists")
        else:
            write(path, content)
            diag.append(path.rsplit("/", 1)[-1] + ":wrote")
        if content.count("(") != content.count(")"):
            diag.append(path.rsplit("/", 1)[-1] + ":UNBALANCED")
            ok = False
        if content.count("{") != content.count("}"):
            diag.append(path.rsplit("/", 1)[-1] + ":BRACES")
            ok = False
    for needle in ("fun testConnection()", "fun save()", "fun trustHostKey()", "fun saveAnyway()"):
        if needle not in VM:
            diag.append("VM:MISSING:" + needle)
            ok = False
    for needle in ("fun WorkspaceSshEditorPage(id: String?)", "private fun SshFormCard", "private fun HostKeyDialog"):
        if needle not in PAGE:
            diag.append("PAGE:MISSING:" + needle[:30])
            ok = False

    diag.append("RESULT:" + ("OK" if ok else "FAIL"))
    with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
        f.write("\n".join(diag) + "\n")
    print(" | ".join(diag))
    if not ok:
        print("::error title=batch352a::" + " | ".join(diag))


main()
