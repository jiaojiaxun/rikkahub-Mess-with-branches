#!/usr/bin/env python3
# rhRemote356c: 跳板机编辑页 UI + VM 状态 (整文件替换 352a 版本)
# VM: JumpHostForm + 跳板地址变更清指纹 + PendingHostKey.jumpHost + trustHostKey 分流
# Page: JumpHostSection (开关+字段) + HostKeyDialog 文案区分跳板
import os

MARK = "rhRemote356c"
DIAG = "ci_diag_batch356c_remote.txt"
ROOT = os.environ.get("GITHUB_WORKSPACE", os.getcwd())


def log(msg):
    print(msg)


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


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
import me.rerere.rikkahub.data.model.SshJumpHostDraft
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
                            jumpHost = settings.jumpHost?.let { jump ->
                                JumpHostForm(
                                    enabled = true,
                                    host = jump.host,
                                    port = jump.port.toString(),
                                    username = jump.username,
                                    authType = jump.authType,
                                    hostKey = jump.hostKey,
                                    hasSavedPassword = jump.encryptedPassword != null,
                                    hasSavedPrivateKey = jump.encryptedPrivateKey != null,
                                )
                            } ?: JumpHostForm(),
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
            // 跳板机的指纹属于原来的地址, 跳板地址变了必须重新确认
            val jumpChanged = new.jumpHost.enabled && old.jumpHost.enabled &&
                (new.jumpHost.host.trim() != old.jumpHost.host.trim() || new.jumpHost.port != old.jumpHost.port)
            if (jumpChanged) {
                new = new.copy(jumpHost = new.jumpHost.copy(hostKey = null), probeResult = null)
            }
            // 经跳板机时目标地址由跳板机解析, 开关跳板或换了跳板, 同一个地址也可能是另一台机器
            if (
                new.host.trim() != old.host.trim() || new.port != old.port ||
                new.jumpHost.enabled != old.jumpHost.enabled || jumpChanged
            ) {
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
        if (state.value.toDraftOrNull()?.withoutHostKeys() != pending.draft.withoutHostKeys()) {
            _state.update { it.copy(pendingHostKey = null) }
            return
        }
        _state.update {
            if (pending.jumpHost) {
                it.copy(jumpHost = it.jumpHost.copy(hostKey = pending.actual), pendingHostKey = null)
            } else {
                it.copy(hostKey = pending.actual, pendingHostKey = null)
            }
        }
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
            val message = if (current.isJumpTargetValid()) {
                R.string.workspace_ssh_editor_missing_jump_fields
            } else {
                R.string.workspace_ssh_editor_missing_fields
            }
            _state.update { it.copy(error = SshEditorError.Resource(message)) }
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
                    it.copy(
                        testing = false,
                        pendingHostKey = PendingHostKey(draft, e.hostKey, null, saveAfter, e.jumpHost),
                    )
                }
            } catch (e: SshHostKeyChangedException) {
                _state.update {
                    it.copy(
                        testing = false,
                        pendingHostKey = PendingHostKey(draft, e.actual, e.expected, saveAfter, e.jumpHost),
                    )
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

    private fun WorkspaceSshEditorState.isJumpTargetValid(): Boolean =
        port.toPortOrNull() != null && host.isNotBlank() && username.isNotBlank()

    private fun WorkspaceSshEditorState.toDraftOrNull(): SshWorkspaceDraft? {
        val port = port.toPortOrNull() ?: return null
        if (host.isBlank() || username.isBlank()) return null
        val jump = if (jumpHost.enabled) {
            jumpHost.toDraftOrNull() ?: return null
        } else {
            null
        }
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
            jumpHost = jump,
        )
    }

    private fun JumpHostForm.toDraftOrNull(): SshJumpHostDraft? {
        val port = port.toPortOrNull() ?: return null
        if (host.isBlank() || username.isBlank()) return null
        return SshJumpHostDraft(
            host = host,
            port = port,
            username = username,
            authType = authType,
            password = password,
            privateKey = privateKey,
            passphrase = passphrase,
            hostKey = hostKey,
        )
    }

    private fun String.toPortOrNull(): Int? = trim().toIntOrNull()?.takeIf { it in 1..65535 }

    private fun SshWorkspaceDraft.withoutHostKeys() =
        copy(hostKey = null, jumpHost = jumpHost?.copy(hostKey = null))
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
    // 编辑已有工作区时, 已保存的凭据可以留空沿用
    val hasSavedPassword: Boolean = false,
    val hasSavedPrivateKey: Boolean = false,
    val jumpHost: JumpHostForm = JumpHostForm(),
    val testing: Boolean = false,
    val saving: Boolean = false,
    val probeResult: SshProbeResult? = null,
    val pendingHostKey: PendingHostKey? = null,
    val error: SshEditorError? = null,
    /** 保存前测试失败的配置, 用户可以选择仍然保存它 */
    val saveAnywayDraft: SshWorkspaceDraft? = null,
    val saved: Boolean = false,
) {
    val busy: Boolean
        get() = loading || testing || saving

    val canSaveAnyway: Boolean
        get() = saveAnywayDraft != null
}

/** 跳板机表单; 关掉开关时保留填过的内容, 保存时不写入 */
data class JumpHostForm(
    val enabled: Boolean = false,
    val host: String = "",
    val port: String = "22",
    val username: String = "",
    val authType: SshAuthType = SshAuthType.PASSWORD,
    val password: String = "",
    val privateKey: String = "",
    val passphrase: String = "",
    val hostKey: SshHostKey? = null,
    val hasSavedPassword: Boolean = false,
    val hasSavedPrivateKey: Boolean = false,
)

/** 表单自己的提示用字符串资源, 连接和保存失败时直接显示异常信息 */
sealed interface SshEditorError {
    data class Resource(@StringRes val id: Int) : SshEditorError

    data class Message(val text: String) : SshEditorError
}

/**
 * 等待用户确认的主机密钥, 属于 [draft] 这份配置; [expected] 不为空表示和之前信任的不一致,
 * [jumpHost] 表示是跳板机的密钥
 */
data class PendingHostKey(
    val draft: SshWorkspaceDraft,
    val actual: SshHostKey,
    val expected: SshHostKey?,
    val saveAfter: Boolean,
    val jumpHost: Boolean = false,
) {
    val address: String
        get() = if (jumpHost) {
            draft.jumpHost?.let { "${it.host}:${it.port}" }.orEmpty()
        } else {
            "${draft.host}:${draft.port}"
        }
}
'''

STRINGS_EN = r'''  <string name="workspace_ssh_editor_jump_host">Jump host</string>
  <string name="workspace_ssh_editor_jump_host_enable">Connect via jump host</string>
  <string name="workspace_ssh_editor_jump_host_enable_desc">Connect to the jump host first, then reach the server through it (like OpenSSH ProxyJump). The host address above is resolved by the jump host.</string>
  <string name="workspace_ssh_editor_jump_host_key">Jump host key</string>
  <string name="workspace_ssh_editor_target_host_key">Target host key</string>
  <string name="workspace_ssh_editor_jump_host_key_confirm">Confirm jump host key</string>
  <string name="workspace_ssh_editor_jump_host_key_changed">Jump host key changed</string>
  <string name="workspace_ssh_editor_missing_jump_fields">Please fill in the jump host fields (host, port and username)</string>
'''
STRINGS_ZH = r'''  <string name="workspace_ssh_editor_jump_host">跳板机</string>
  <string name="workspace_ssh_editor_jump_host_enable">通过跳板机连接</string>
  <string name="workspace_ssh_editor_jump_host_enable_desc">先连接跳板机，再经它访问服务器，相当于 OpenSSH 的 ProxyJump。上方的主机地址由跳板机解析。</string>
  <string name="workspace_ssh_editor_jump_host_key">跳板机密钥</string>
  <string name="workspace_ssh_editor_target_host_key">目标主机密钥</string>
  <string name="workspace_ssh_editor_jump_host_key_confirm">确认跳板机密钥</string>
  <string name="workspace_ssh_editor_jump_host_key_changed">跳板机密钥已变化</string>
  <string name="workspace_ssh_editor_missing_jump_fields">请填写跳板机的主机、端口和用户名</string>
'''

# Page 修改: 在认证卡与工作目录卡之间插入跳板机分组; 安全卡标题按跳板开关切换; HostKeyDialog 文案区分
PAGE_ANCHOR_WORKDIR = """            item {
                SshFormCard(title = stringResource(R.string.workspace_ssh_editor_working_dir)) {"""
PAGE_JUMP_SECTION = r'''            item {
                JumpHostSection(
                    jump = state.jumpHost,
                    enabled = editable,
                    onUpdate = { transform -> vm.update { it.copy(jumpHost = transform(it.jumpHost)) } },
                    onImportPrivateKey = { jumpPrivateKeyPicker.launch(arrayOf("*/*")) },
                )
            }

''' + PAGE_ANCHOR_WORKDIR

PAGE_ANCHOR_PICKER = """    val privateKeyPicker = rememberPrivateKeyPicker { key -> vm.update { it.copy(privateKey = key) } }
"""
PAGE_PICKER_NEW = PAGE_ANCHOR_PICKER + """    val jumpPrivateKeyPicker = rememberPrivateKeyPicker { key ->
        vm.update { it.copy(jumpHost = it.jumpHost.copy(privateKey = key)) }
    }
"""

PAGE_ANCHOR_SECURITY = """                SshFormCard(title = stringResource(R.string.workspace_ssh_editor_security)) {
                    Text(
                        text = stringResource(R.string.workspace_ssh_editor_host_key),
                        style = MaterialTheme.typography.titleSmall,
                    )
"""
PAGE_SECURITY_NEW = """                SshFormCard(title = stringResource(R.string.workspace_ssh_editor_security)) {
                    Text(
                        text = stringResource(
                            if (state.jumpHost.enabled) R.string.workspace_ssh_editor_target_host_key
                            else R.string.workspace_ssh_editor_host_key
                        ),
                        style = MaterialTheme.typography.titleSmall,
                    )
"""

JUMP_HOST_SECTION = r'''
@Composable
private fun JumpHostSection(
    jump: JumpHostForm,
    enabled: Boolean,
    onUpdate: ((JumpHostForm) -> JumpHostForm) -> Unit,
    onImportPrivateKey: () -> Unit,
) {
    SshFormCard(title = stringResource(R.string.workspace_ssh_editor_jump_host)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = stringResource(R.string.workspace_ssh_editor_jump_host_enable),
                    style = MaterialTheme.typography.bodyMedium,
                )
                Text(
                    text = stringResource(R.string.workspace_ssh_editor_jump_host_enable_desc),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            androidx.compose.material3.Switch(
                checked = jump.enabled,
                onCheckedChange = { checked -> onUpdate { it.copy(enabled = checked) } },
                enabled = enabled,
            )
        }
        if (!jump.enabled) return@SshFormCard
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(
            enabled = enabled,
            value = jump.host,
            onValueChange = { value -> onUpdate { it.copy(host = value.trim()) } },
            modifier = Modifier.fillMaxWidth(),
            label = { Text(stringResource(R.string.workspace_ssh_editor_host)) },
            placeholder = { Text("bastion.example.com") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
        )
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(
            enabled = enabled,
            value = jump.port,
            onValueChange = { value ->
                onUpdate { it.copy(port = value.filter(Char::isDigit).take(5)) }
            },
            modifier = Modifier.fillMaxWidth(),
            label = { Text(stringResource(R.string.workspace_ssh_editor_port)) },
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
        )
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(
            enabled = enabled,
            value = jump.username,
            onValueChange = { value -> onUpdate { it.copy(username = value.trim()) } },
            modifier = Modifier.fillMaxWidth(),
            label = { Text(stringResource(R.string.workspace_ssh_editor_username)) },
            singleLine = true,
        )
        Spacer(Modifier.height(8.dp))
        SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {
            val options = listOf(
                SshAuthType.PASSWORD to stringResource(R.string.workspace_ssh_editor_password),
                SshAuthType.PRIVATE_KEY to stringResource(R.string.workspace_ssh_editor_private_key),
            )
            options.forEachIndexed { index, (type, label) ->
                SegmentedButton(
                    enabled = enabled,
                    selected = jump.authType == type,
                    onClick = { onUpdate { it.copy(authType = type) } },
                    shape = SegmentedButtonDefaults.itemShape(index, options.size),
                ) {
                    Text(label)
                }
            }
        }
        Spacer(Modifier.height(8.dp))
        when (jump.authType) {
            SshAuthType.PASSWORD -> SecretTextField(
                enabled = enabled,
                value = jump.password,
                onValueChange = { value -> onUpdate { it.copy(password = value) } },
                label = stringResource(R.string.workspace_ssh_editor_password),
                placeholder = if (jump.hasSavedPassword) {
                    stringResource(R.string.workspace_ssh_editor_saved_keep)
                } else {
                    null
                },
            )

            SshAuthType.PRIVATE_KEY -> {
                OutlinedTextField(
                    enabled = enabled,
                    value = jump.privateKey,
                    onValueChange = { value -> onUpdate { it.copy(privateKey = value) } },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text(stringResource(R.string.workspace_ssh_editor_private_key)) },
                    placeholder = {
                        Text(
                            if (jump.hasSavedPrivateKey) {
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
                    enabled = enabled,
                    onClick = onImportPrivateKey,
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
                    enabled = enabled,
                    value = jump.passphrase,
                    onValueChange = { value -> onUpdate { it.copy(passphrase = value) } },
                    label = stringResource(R.string.workspace_ssh_editor_passphrase),
                    placeholder = stringResource(R.string.workspace_ssh_editor_passphrase_placeholder),
                )
            }
        }
        Spacer(Modifier.height(8.dp))
        Text(
            text = stringResource(R.string.workspace_ssh_editor_jump_host_key),
            style = MaterialTheme.typography.titleSmall,
        )
        Spacer(Modifier.height(4.dp))
        if (jump.hostKey == null) {
            Text(
                text = stringResource(R.string.workspace_ssh_editor_host_key_unconfirmed),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        } else {
            Text(
                text = "${jump.hostKey?.type}\n${jump.hostKey?.fingerprint}",
                style = MaterialTheme.typography.bodySmall,
                fontFamily = FontFamily.Monospace,
            )
        }
    }
}
'''

# HostKeyDialog 标题区分跳板
DIALOG_ANCHOR = """        title = {
            Text(
                stringResource(
                    if (changed) R.string.workspace_ssh_editor_host_key_changed
                    else R.string.workspace_ssh_editor_host_key_confirm
                )
            )
        },"""
DIALOG_NEW = """        title = {
            Text(
                stringResource(
                    when {
                        pending.jumpHost && changed -> R.string.workspace_ssh_editor_jump_host_key_changed
                        pending.jumpHost -> R.string.workspace_ssh_editor_jump_host_key_confirm
                        changed -> R.string.workspace_ssh_editor_host_key_changed
                        else -> R.string.workspace_ssh_editor_host_key_confirm
                    }
                )
            )
        },"""


def main():
    diag = []
    ok = True

    # VM 整文件替换
    vm_path = "app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/WorkspaceSshEditorVM.kt"
    write(vm_path, VM)
    diag.append("vm:wrote " + str(len(VM)))
    if VM.count("(") != VM.count(")") or VM.count("{") != VM.count("}"):
        diag.append("vm:UNBALANCED")
        ok = False
    for needle in ("data class JumpHostForm(", "val jumpHost: JumpHostForm = JumpHostForm()",
                   "if (pending.jumpHost)", "e.jumpHost)", "jumpHost?.toSettings(previous?.jumpHost)"):
        if needle not in VM:
            diag.append("vm:MISSING:" + needle[:30])
            ok = False

    # Page 锚点修改
    page_path = "app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/WorkspaceSshEditorPage.kt"
    page = read(page_path)
    for label, needle, repl in (
        ("page-picker", PAGE_ANCHOR_PICKER, PAGE_PICKER_NEW),
        ("page-jump", PAGE_ANCHOR_WORKDIR, PAGE_JUMP_SECTION),
        ("page-security", PAGE_ANCHOR_SECURITY, PAGE_SECURITY_NEW),
        ("page-dialog", DIALOG_ANCHOR, DIALOG_NEW),
    ):
        if repl in page:
            diag.append(label + ":already")
            continue
        if page.count(needle) != 1:
            diag.append(label + ":ANCHOR-MISMATCH(" + str(page.count(needle)) + ")")
            ok = False
            continue
        page = page.replace(needle, repl, 1)
        diag.append(label + ":ok")
    # 追加 JumpHostSection 组件到文件末尾
    if "private fun JumpHostSection(" not in page:
        page = page.rstrip() + "\n" + JUMP_HOST_SECTION
        diag.append("page-section:appended")
    write(page_path, page)

    # strings
    for path, block, label in (
        ("app/src/main/res/values/strings.xml", STRINGS_EN, "strings-en"),
        ("app/src/main/res/values-zh/strings.xml", STRINGS_ZH, "strings-zh"),
    ):
        text = read(path)
        if 'name="workspace_ssh_editor_jump_host"' in text:
            diag.append(label + ":already")
            continue
        anchor = "</resources>"
        if text.count(anchor) != 1:
            diag.append(label + ":ANCHOR-MISMATCH")
            ok = False
            continue
        text = text.replace(anchor, block + "\n" + anchor, 1)
        write(path, text)
        diag.append(label + ":ok")

    # 自检
    final_page = read(page_path)
    for needle in ("JumpHostSection(", "jumpPrivateKeyPicker", "target_host_key", "jump_host_key_changed"):
        if needle not in final_page:
            diag.append("page:MISSING:" + needle[:30])
            ok = False
    if JUMP_HOST_SECTION.count("(") != JUMP_HOST_SECTION.count(")"):
        diag.append("section:UNBALANCED")
        ok = False

    diag.append("RESULT:" + ("OK" if ok else "FAIL"))
    with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
        f.write("\n".join(diag) + "\n")
    log(" | ".join(diag))
    if not ok:
        print("::error title=batch356c::" + " | ".join(diag))


main()
